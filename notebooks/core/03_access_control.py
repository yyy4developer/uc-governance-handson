# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — アクセス制御（ABAC / ポリシーベース）
# MAGIC
# MAGIC Unity Catalog の **属性ベースアクセス制御（ABAC）** を体験します。
# MAGIC 従来は「テーブルごとに `SET ROW FILTER` / `SET MASK` を個別付与」でしたが、ABAC では
# MAGIC **管理タグ（Governed Tag）を列に付け、タグに対してポリシーを1本張る**だけで、
# MAGIC 対象スキーマ配下の**該当タグを持つ全テーブル・全列に自動適用**されます（付け外しはタグ操作だけ）。
# MAGIC
# MAGIC 1. **階層的な GRANT**（カタログ → スキーマ → テーブル、権限は継承）
# MAGIC 2. **管理タグ（Governed Tag）の作成**（UI / SQL 両方）
# MAGIC 3. **Tag Policies — 許可値による統制**（タグの付け間違い・表記ゆれを防ぐ）
# MAGIC 4. **列へのタグ付与**
# MAGIC 5. **タグ駆動の列マスク（ABAC COLUMN MASK ポリシー）**: `uc_handson_pii=confidential` タグの付いた列を自動マスク
# MAGIC 6. **タグ駆動の行フィルタ（ABAC ROW FILTER ポリシー）**: `uc_handson_segment` タグの付いた列で行を制御
# MAGIC 7. **適用中のポリシー一覧**
# MAGIC 8. **後片付け**（04 を壊さないため、ポリシーとタグを必ず解除）
# MAGIC
# MAGIC ペルソナ（グループ）: `data_governance_admins` / `sales_automobile` / `sales_building` / `sales_machinery`
# MAGIC
# MAGIC > 📖 [属性ベースのアクセス制御 (ABAC)](https://docs.databricks.com/ja/data-governance/unity-catalog/abac/index.html) ／
# MAGIC > [行フィルタ・列マスクポリシーの管理](https://docs.databricks.com/ja/data-governance/unity-catalog/abac/policies.html) ／
# MAGIC > [管理タグ (Governed Tags)](https://docs.databricks.com/ja/admin/governed-tags/) ／
# MAGIC > [CREATE GOVERNED TAG](https://docs.databricks.com/ja/sql/language-manual/sql-ref-syntax-ddl-create-governed-tag.html)
# MAGIC
# MAGIC ⚠️ **ABAC は Governed Tag（管理タグ）が必須**（通常のタグ不可）。管理タグはアカウント単位で共有されるため、
# MAGIC このデモでは衝突回避のため専用キー `uc_handson_pii` / `uc_handson_segment` を使います。
# MAGIC
# MAGIC ⚠️ **構文メモ**: `CREATE / DROP / SHOW POLICY ... ON SCHEMA` は **修飾名を直書き**します
# MAGIC （`IDENTIFIER()` 関数や `:catalog` パラメタは不可）。本ノートブックはポリシー系を Python の
# MAGIC f-string（`spark.sql(...)`）で組み立て、`_config` が定義した `catalog` / `schema` / `FQ` を埋め込みます。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# _config が catalog / schema / FQ を定義し、USE CATALOG / USE SCHEMA まで実行済み
# FQ = f"{catalog}.{schema}"
print(f"target = {FQ}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. 実行者のグループ所属を確認
# MAGIC
# MAGIC ABAC ポリシーは `is_account_group_member(...)` でアクセス可否を判定します。まず自分がどのグループに
# MAGIC 属しているかを確認します。**多くの sandbox では下記が全て `false`** になります
# MAGIC （workspace admin ≠ アカウントグループ `admins`）。その場合、この後のポリシー適用で
# MAGIC **自分自身がマスク/フィルタされる側**になり、「ABAC が効いている」様子をそのまま観察できます。

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   current_user()                                    AS me,
# MAGIC   is_account_group_member('admins')                 AS in_admins,
# MAGIC   is_account_group_member('data_governance_admins') AS in_dga,
# MAGIC   is_account_group_member('sales_automobile')       AS in_sales_automobile;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 階層的な GRANT
# MAGIC
# MAGIC カタログ/スキーマへの `USE` と、テーブルへの `SELECT` を付与します。権限は階層で継承されます。
# MAGIC （グループ名は環境に合わせて置き換えてください。存在しない場合は手順の理解に留めます）

# COMMAND ----------

# MAGIC %md
# MAGIC ```sql
# MAGIC -- 例: データガバナンス管理者にスキーマ全体の参照を付与
# MAGIC GRANT USE CATALOG ON CATALOG <catalog> TO `data_governance_admins`;
# MAGIC GRANT USE SCHEMA  ON SCHEMA  <catalog>.<schema> TO `data_governance_admins`;
# MAGIC GRANT SELECT      ON SCHEMA  <catalog>.<schema> TO `data_governance_admins`;
# MAGIC
# MAGIC -- 営業（セグメント別）には顧客・受注を参照付与（行は後述の行フィルタで自動的に絞られる）
# MAGIC GRANT SELECT ON TABLE <catalog>.<schema>.customer TO `sales_automobile`;
# MAGIC GRANT SELECT ON TABLE <catalog>.<schema>.orders   TO `sales_automobile`;
# MAGIC ```

# COMMAND ----------

def _grant(stmt: str):
    try:
        spark.sql(stmt); print("✓", stmt)
    except Exception as e:
        print("· skip:", str(e).splitlines()[0][:90])

try:
    have = {r["name"] for r in spark.sql("SHOW GROUPS").collect()}
except Exception:
    have = set()

if "data_governance_admins" in have:
    _grant(f"GRANT USE CATALOG ON CATALOG {catalog} TO `data_governance_admins`")
    _grant(f"GRANT USE SCHEMA ON SCHEMA {FQ} TO `data_governance_admins`")
    _grant(f"GRANT SELECT ON SCHEMA {FQ} TO `data_governance_admins`")
else:
    print("· デモ用グループが見つかりません。上の SQL 例で手順を確認してください（ABAC ポリシーはグループが無くても作成・適用でき、効果も観察できます）。")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 管理タグ（Governed Tag）の作成
# MAGIC
# MAGIC ABAC の起点は **管理タグ**。ここでは 2 種類を作成します。
# MAGIC - `uc_handson_pii` … 機微情報の列に付ける（値: `confidential` / `restricted`）→ 列マスクの対象
# MAGIC - `uc_handson_segment` … 行フィルタの判定に使う列に付ける（値: `segment_key`）→ 行フィルタの対象
# MAGIC
# MAGIC > `CREATE GOVERNED TAG` は `IF NOT EXISTS` 非対応 / `DESCRIPTION` と `VALUES` を使用（`COMMENT`/`ALLOWED VALUES` ではない）。
# MAGIC
# MAGIC 🧑‍🤝‍🧑 **ハンズオンでの注意**: 管理タグは**アカウント全体で共有**されるリソースです。
# MAGIC そのため、**最初に実行した人がタグを作成し、2人目以降は「既に存在します」と表示されます**（正常な動作）。
# MAGIC タグは全員で共通のものを使い、**ポリシーは各自のスキーマに張る**ので、お互いの作業には影響しません。
# MAGIC 下のセルはどちらの場合も成功扱いになるので、そのまま次へ進んでください。

# COMMAND ----------

# 管理タグはアカウント共有リソース。2人目以降は ALREADY_EXISTS になるが、
# 既存タグをそのまま使えばよいので握りつぶして続行する。
for stmt in [
    "CREATE GOVERNED TAG uc_handson_pii "
    "DESCRIPTION 'ABAC demo: PII / confidential column marker' "
    "VALUES ('confidential','restricted')",
    "CREATE GOVERNED TAG uc_handson_segment "
    "DESCRIPTION 'ABAC demo: row-level segment control column marker' "
    "VALUES ('segment_key')",
]:
    tag_name = stmt.split()[3]
    try:
        spark.sql(stmt)
        print(f"✓ 管理タグを作成しました: {tag_name}")
    except Exception as e:
        if "ALREADY_EXISTS" in str(e) or "already exists" in str(e).lower():
            print(f"✓ 管理タグは既に存在します（他の参加者が作成済み）: {tag_name} — そのまま使えます")
        else:
            print(f"⚠️ {tag_name}: {str(e).splitlines()[0][:100]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🖱️ UI で管理タグを作る／確認する（Catalog Explorer）
# MAGIC
# MAGIC 上のセルは SQL で作りましたが、**管理タグは UI から作成・管理できます**。
# MAGIC
# MAGIC 1. 左メニュー **Catalog** を開く
# MAGIC 2. 上部の **Govern**（盾アイコン）をクリック
# MAGIC 3. ドロップダウンから **Governed Tags** を選択
# MAGIC 4. **Create governed tag** をクリック
# MAGIC 5. **Tag key**（例 `uc_handson_pii`）、任意で **Description**、そして **Allowed values** を入力
# MAGIC 6. **Create** をクリック
# MAGIC
# MAGIC → いま作成した `uc_handson_pii` / `uc_handson_segment` がこの一覧に見えるはずです。クリックすると
# MAGIC 許可値や、そのタグがどこで使われているか（利用状況）を確認できます。
# MAGIC
# MAGIC > 作成できるのは **アカウント管理者とワークスペース管理者**（既定で `CREATE` 権限あり）。
# MAGIC > 管理タグは**アカウント全体**に効くので、組織横断のタグ統制はここで一元管理します。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. タグの「許可値」で統制する（Tag Policies）
# MAGIC
# MAGIC ここが**組織スケールでガバナンスを効かせる鍵**です。
# MAGIC 管理タグは単なるラベルではなく、**許可値（Allowed values）を定義できます**。
# MAGIC こうすると「タグの付け間違い」「表記ゆれ」を**システム側で防止**できます。
# MAGIC
# MAGIC | | 通常のタグ | 管理タグ + 許可値 |
# MAGIC |---|---|---|
# MAGIC | 値の制約 | なし（何でも入る） | **定義した値のみ** |
# MAGIC | 表記ゆれ | `confidential` / `Confidential` / `機密` が混在 | 統一される |
# MAGIC | ABAC ポリシー | 使えない | **使える** |
# MAGIC
# MAGIC `uc_handson_pii` には `confidential` / `restricted` のみ許可しました。
# MAGIC **許可していない値を入れようとすると、実際にエラーになります** — 下のセルで体験してみましょう。

# COMMAND ----------

# 許可値の外側の値を入れてみる → 弾かれることを確認（これが Tag Policy の効果）
try:
    spark.sql(
        "ALTER TABLE customer ALTER COLUMN c_acctbal "
        "SET TAGS ('uc_handson_pii' = 'ちょっと秘密')"
    )
    print("⚠️ 通ってしまいました（許可値の設定を確認してください）")
except Exception as e:
    msg = str(e).splitlines()[0]
    print("✓ 想定どおり弾かれました — これが Tag Policy による統制です")
    print(f"  → {msg[:180]}")

# COMMAND ----------

# MAGIC %md
# MAGIC 💡 **なぜ重要か**: 部門ごとに好きな値でタグを付けていくと、半年後には
# MAGIC `confidential` / `CONFIDENTIAL` / `機密` / `secret` が混在し、
# MAGIC 「機密データを一覧する」ことすらできなくなります。
# MAGIC 許可値を決めておけば、**タグは常に検索・ポリシー適用できる状態**に保たれます。
# MAGIC
# MAGIC UI で許可値を変えたいときは、**Catalog → Govern → Governed Tags → 対象タグ → Edit** から
# MAGIC 値の追加・削除ができます（SQL なら `ALTER GOVERNED TAG <key> SET VALUES (...)`）。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. 列にタグを付与
# MAGIC
# MAGIC `customer` の 2 列にタグを付けます。**この時点ではまだデータは変わりません**（ポリシーを張って初めて効きます）。
# MAGIC - `c_acctbal`（口座残高＝機微情報） ← `uc_handson_pii = confidential`
# MAGIC - `c_mktsegment`（市場セグメント） ← `uc_handson_segment = segment_key`

# COMMAND ----------

# MAGIC %sql
# MAGIC ALTER TABLE customer ALTER COLUMN c_acctbal   SET TAGS ('uc_handson_pii'     = 'confidential');

# COMMAND ----------

# MAGIC %sql
# MAGIC ALTER TABLE customer ALTER COLUMN c_mktsegment SET TAGS ('uc_handson_segment' = 'segment_key');

# COMMAND ----------

# 付与されたタグを確認
display(spark.sql(f"""
  SELECT column_name, tag_name, tag_value
  FROM system.information_schema.column_tags
  WHERE catalog_name = '{catalog}' AND schema_name = '{schema}' AND table_name = 'customer'
    AND tag_name IN ('uc_handson_pii','uc_handson_segment')
  ORDER BY column_name
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. タグ駆動の列マスク（ABAC COLUMN MASK ポリシー）
# MAGIC
# MAGIC マスク関数を定義し、**`uc_handson_pii = confidential` タグを持つ列すべて**にポリシーを1本張ります。
# MAGIC `MATCH COLUMNS` がタグ条件、`ON COLUMN` がマッチした列を指します。
# MAGIC 管理者（`admins` / `data_governance_admins`）は実値、それ以外は `NULL` にマスクされます。

# COMMAND ----------

# MAGIC %sql
# MAGIC -- マスク関数（管理者は実値、それ以外は NULL）
# MAGIC CREATE OR REPLACE FUNCTION mask_pii_num(v DECIMAL(18,2))
# MAGIC RETURN CASE
# MAGIC   WHEN is_account_group_member('admins')
# MAGIC     OR is_account_group_member('data_governance_admins') THEN v
# MAGIC   ELSE NULL
# MAGIC END;

# COMMAND ----------

# スキーマ配下で「uc_handson_pii=confidential タグの付いた列」に自動でマスクを適用
# ※ ON SCHEMA は修飾名を直書き（IDENTIFIER 不可）。f-string で FQ を埋め込む。
spark.sql(f"""
  CREATE OR REPLACE POLICY mask_pii_columns
  ON SCHEMA {FQ}
  COMMENT 'Mask any column tagged uc_handson_pii=confidential for non-admins'
  COLUMN MASK mask_pii_num
  TO `account users`
  FOR TABLES
  MATCH COLUMNS has_tag_value('uc_handson_pii', 'confidential') AS c
  ON COLUMN c
""")
print("✓ policy mask_pii_columns created")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 効果確認: 非 admin なら c_acctbal が NULL に、admin なら実値
# MAGIC SELECT c_custkey, c_name, c_mktsegment, c_acctbal
# MAGIC FROM customer LIMIT 10;

# COMMAND ----------

# MAGIC %md
# MAGIC 💡 **ABAC の威力**: 同じタグ `uc_handson_pii=confidential` を別テーブルの列（例 `supplier.s_acctbal`）に
# MAGIC 付けると、**新しいポリシーを書かずに**その列も自動的にマスクされます。試しに下を実行して確認できます
# MAGIC （後片付けで戻します）。

# COMMAND ----------

# MAGIC %sql
# MAGIC -- （任意）supplier の残高列にも同じタグ → 同一ポリシーが自動適用される
# MAGIC ALTER TABLE supplier ALTER COLUMN s_acctbal SET TAGS ('uc_handson_pii' = 'confidential');

# COMMAND ----------

# MAGIC %sql
# MAGIC -- supplier.s_acctbal も（非 admin なら）NULL にマスクされている＝ポリシー追加不要
# MAGIC SELECT s_suppkey, s_name, s_acctbal FROM supplier LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. タグ駆動の行フィルタ（ABAC ROW FILTER ポリシー）
# MAGIC
# MAGIC 「営業は担当する市場セグメントの顧客のみ閲覧」を **行フィルタ関数 + タグ駆動ポリシー** で実現します。
# MAGIC `uc_handson_segment` タグの付いた列（＝ `c_mktsegment`）をフィルタ関数の引数に渡します。
# MAGIC 管理者は全件、営業は所属グループのセグメントのみ、どちらでもなければ 0 件になります。

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 行フィルタ関数: 管理者は全件、それ以外はセグメント別グループに応じて限定
# MAGIC CREATE OR REPLACE FUNCTION row_filter_by_segment(segment STRING)
# MAGIC RETURN
# MAGIC   is_account_group_member('admins')
# MAGIC   OR is_account_group_member('data_governance_admins')
# MAGIC   OR (segment = 'AUTOMOBILE' AND is_account_group_member('sales_automobile'))
# MAGIC   OR (segment = 'BUILDING'   AND is_account_group_member('sales_building'))
# MAGIC   OR (segment = 'MACHINERY'  AND is_account_group_member('sales_machinery'));

# COMMAND ----------

# スキーマ配下で「uc_handson_segment タグの付いた列」を引数に行フィルタを自動適用
spark.sql(f"""
  CREATE OR REPLACE POLICY row_filter_segment
  ON SCHEMA {FQ}
  COMMENT 'Row filter on columns tagged uc_handson_segment'
  ROW FILTER row_filter_by_segment
  TO `account users`
  FOR TABLES
  MATCH COLUMNS has_tag_value('uc_handson_segment', 'segment_key') AS seg
  USING COLUMNS (seg)
""")
print("✓ policy row_filter_segment created")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 効果確認: 管理者なら全セグメント、非該当グループなら 0 件
# MAGIC SELECT c_mktsegment, count(*) AS n
# MAGIC FROM customer GROUP BY c_mktsegment ORDER BY c_mktsegment;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. 適用中のポリシー一覧
# MAGIC
# MAGIC スキーマに張られている ABAC ポリシーを確認します。

# COMMAND ----------

display(spark.sql(f"SHOW POLICIES ON SCHEMA {FQ}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. 後片付け（⚠️ 必ず実行してから 04 へ進む）
# MAGIC
# MAGIC **重要**: 行フィルタ/列マスクポリシーを張ったまま次の `04_lineage` に進むと、実行者が対象グループに
# MAGIC 属していない場合 `customer` が **0 行 / c_acctbal が NULL** に見え、
# MAGIC **04 の JOIN 結果（order_analysis_summary）が空になります**。
# MAGIC ここでポリシーと列タグを外し、素の状態（750,000 行・実値）に戻します。
# MAGIC （マスク関数 `mask_pii_num` / フィルタ関数 `row_filter_by_segment`、管理タグ定義は残るので再適用はいつでも可能）

# COMMAND ----------

# DROP POLICY は IF EXISTS 非対応のため try/except でラップ
for pol in ["mask_pii_columns", "row_filter_segment"]:
    try:
        spark.sql(f"DROP POLICY {pol} ON SCHEMA {FQ}")
        print("✓ dropped policy:", pol)
    except Exception as e:
        print("· skip:", str(e).splitlines()[0][:90])

# 付与した列タグを解除（任意で追加した supplier.s_acctbal も戻す）
for tbl, col, tag in [
    ("customer", "c_acctbal",   "uc_handson_pii"),
    ("customer", "c_mktsegment", "uc_handson_segment"),
    ("supplier", "s_acctbal",   "uc_handson_pii"),
]:
    try:
        spark.sql(f"ALTER TABLE {tbl} ALTER COLUMN {col} UNSET TAGS ('{tag}')")
        print(f"✓ untagged: {tbl}.{col}")
    except Exception as e:
        print("· skip:", str(e).splitlines()[0][:90])

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 全件・実値に戻ったことを確認（750,000 行 / c_acctbal に値）
# MAGIC SELECT count(*) AS rows, max(c_acctbal) AS max_bal FROM customer;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で設定する手順（Catalog Explorer）
# MAGIC
# MAGIC 上のセルは SQL で設定しましたが、**GRANT・タグ付与・ポリシー作成は UI からも操作**できます。
# MAGIC
# MAGIC **A. GRANT を UI で付与する（コード不要）**
# MAGIC 1. **Catalog** → 対象スキーマ → テーブル → **Permissions** タブ → **Grant**
# MAGIC 2. **Principals** で付与先グループ、**Privileges** で `SELECT` にチェック → **Grant**
# MAGIC 3. カタログ/スキーマ単位で付けると下位に継承。取り消しは **Revoke**
# MAGIC
# MAGIC **B. 管理タグを UI で列に付ける**
# MAGIC 1. `customer` テーブル → **Columns**（または Overview）タブ → 対象列（`c_acctbal`）の行
# MAGIC 2. 右端 **⋮ → Edit tags**（またはタグ列の＋）→ 管理タグ `uc_handson_pii` を選び 値 `confidential` → 保存
# MAGIC 3. 管理タグ自体の作成/許可値の管理は **Catalog Explorer 左下の「Tags」**（または Account 管理）から
# MAGIC
# MAGIC **C. ABAC ポリシーを UI で作る（本ノートブック冒頭のスクショの画面）**
# MAGIC 1. **Catalog** → 対象カタログ/スキーマ → **Policies**（ポリシー）タブ → **Create policy / 新しいポリシー**
# MAGIC 2. **ポリシーの種類**: 「列マスク」または「行フィルター」を選択
# MAGIC 3. **プリンシパルとスコープ**:
# MAGIC    - 適用対象（TO）に `account users`、除外（EXCEPT）に管理者グループ、を指定できる
# MAGIC    - **範囲（ON）**: カタログ / スキーマ / テーブルを選択（ここでスキーマを選ぶと配下に自動適用）
# MAGIC 4. **タグ条件（MATCH COLUMNS）**: `uc_handson_pii = confidential` のようにタグで対象列を絞り込む
# MAGIC 5. 参照する関数（`mask_pii_num` / `row_filter_by_segment`）を選択 → **ポリシーを作成**
# MAGIC    （右ペインの「コードを表示」で、UI 操作と等価な SQL がリアルタイムに確認できる）
# MAGIC
# MAGIC **D. 効果の確認方法**
# MAGIC - 別ユーザー（各グループ所属）でログインし `SELECT * FROM customer` → 行数・`c_acctbal` の見え方の差を確認
# MAGIC - 管理者は全件・実値、非該当グループは絞り込み・NULL になる
# MAGIC - **ABAC の要点**: タグを別テーブル/別列に付け替えるだけで、ポリシーを増やさず保護範囲が変わる
# MAGIC
# MAGIC 次は **`04_lineage`** で、テーブル間のデータリネージを生成・可視化します。
