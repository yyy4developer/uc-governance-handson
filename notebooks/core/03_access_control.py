# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — アクセス制御（RBAC → タグ → ABAC）
# MAGIC
# MAGIC > 🔑 **必要な権限**: 自分のスキーマの owner ＋ **管理タグの `ASSIGN`**
# MAGIC > （管理タグは**管理者が事前に作成**済みの前提です。タグ作成のセルは
# MAGIC > 「既に存在します」と表示されるのが正常で、そのまま次へ進めます）
# MAGIC
# MAGIC Unity Catalog のアクセス制御を、**2 つの方式**で体験します。
# MAGIC
# MAGIC | | **RBAC**（ロールベース） | **ABAC**（属性ベース） |
# MAGIC |---|---|---|
# MAGIC | 考え方 | 「**誰に**」「**どのオブジェクトへ**」権限を付ける | 「**どんな属性（タグ）を持つ列**」を保護するかを決める |
# MAGIC | 書き方 | `GRANT SELECT ON TABLE ... TO ...` | タグを付け、タグ条件でポリシーを 1 本張る |
# MAGIC | 得意なこと | 明示的で分かりやすい。基本はこれ | **対象が増えても書き換え不要**（大規模向き） |
# MAGIC | 例 | 「営業チームに受注テーブルの参照を許可」 | 「機微とタグ付けした列は、管理者以外マスク」 |
# MAGIC
# MAGIC RBAC が土台で、ABAC は**その上でよりきめ細かく・スケールさせる**ための仕組みです。
# MAGIC
# MAGIC ## このノートブックの流れ
# MAGIC
# MAGIC | # | 内容 | 方式 |
# MAGIC |---|---|---|
# MAGIC | 1 | 自分の権限を確認する（owner とは何か） | RBAC |
# MAGIC | 2 | **GRANT / REVOKE を体験**（階層と継承） | RBAC |
# MAGIC | 3 | **管理タグ（Governed Tag）の確認** — 全員で共有 | 準備 |
# MAGIC | 4 | **Tag Policies — 許可値による統制** | 準備 |
# MAGIC | 5 | テーブル・列へのタグ付与 | 準備 |
# MAGIC | 6 | **タグ駆動の列マスク**（ABAC COLUMN MASK） | ABAC |
# MAGIC | 7 | **タグ駆動の行フィルタ**（ABAC ROW FILTER） | ABAC |
# MAGIC | 8 | 適用中のポリシー一覧 | 確認 |
# MAGIC | 9 | **後片付け**（⚠️ 04 を壊さないため必ず実行） | — |
# MAGIC
# MAGIC ペルソナ（グループ）: `data_governance_admins` / `sales_automobile` / `sales_building` / `sales_machinery`
# MAGIC
# MAGIC > 📖 [権限の管理（GRANT）](https://docs.databricks.com/ja/data-governance/unity-catalog/manage-privileges/index.html) ／
# MAGIC > [属性ベースのアクセス制御 (ABAC)](https://docs.databricks.com/ja/data-governance/unity-catalog/abac/index.html) ／
# MAGIC > [行フィルタ・列マスクポリシー](https://docs.databricks.com/ja/data-governance/unity-catalog/abac/policies.html) ／
# MAGIC > [管理タグ (Governed Tags)](https://docs.databricks.com/ja/admin/governed-tags/)
# MAGIC
# MAGIC ⚠️ **ABAC は管理タグ（Governed Tag）が必須**です（通常のタグでは使えません）。
# MAGIC 管理タグはアカウント単位で共有されるため、衝突回避のため `uc_handson_` prefix を付けています。
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
# MAGIC # 【RBAC パート】
# MAGIC
# MAGIC まずは基本の **RBAC（ロールベースアクセス制御）** —
# MAGIC 「**誰に**」「**何を**」許可するかを明示的に指定する方式です。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 自分の権限を確認する（owner とは何か）
# MAGIC
# MAGIC あなたは自分のスキーマを**自分で作った**ので、そのスキーマの **owner（所有者）** です。
# MAGIC owner は配下のオブジェクトに対してすべての権限を持ちます。
# MAGIC だから今まで GRANT なしでテーブルを作ったり読んだりできていました。

# COMMAND ----------

display(spark.sql(f"SHOW GRANTS ON SCHEMA {FQ}"))

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 自分が誰で、どのグループに属しているか（後の ABAC で使います）
# MAGIC SELECT
# MAGIC   current_user()                                    AS me,
# MAGIC   is_account_group_member('admins')                 AS in_admins,
# MAGIC   is_account_group_member('data_governance_admins') AS in_dga,
# MAGIC   is_account_group_member('sales_automobile')       AS in_sales_automobile;

# COMMAND ----------

# MAGIC %md
# MAGIC 💡 `is_account_group_member(...)` が**すべて `false` でも問題ありません**。
# MAGIC その場合、後半の ABAC で**自分自身がマスク/フィルタされる側**になるので、
# MAGIC 「制御が効いている」様子をそのまま観察できます。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. GRANT を体験する（権限の階層と継承）
# MAGIC
# MAGIC Unity Catalog の権限は **カタログ → スキーマ → テーブル** の階層で継承されます。
# MAGIC 下位のオブジェクトを読むには、**上位への `USE` 権限も必要**です。
# MAGIC
# MAGIC ```
# MAGIC   カタログ    USE CATALOG   ← ここを通れないと中が見えない
# MAGIC     └ スキーマ  USE SCHEMA    ← ここも通る必要がある
# MAGIC         └ テーブル  SELECT      ← 実際に読む権限
# MAGIC ```
# MAGIC
# MAGIC ### 🧑‍🤝‍🧑 参加者グループに付与して、隣の人と確認しましょう
# MAGIC
# MAGIC 自分に対しては常に全権限があるため、**GRANT の効果は他人に付与して初めて体感できます**。
# MAGIC ここでは**参加者グループ（`PARTICIPANT_GROUP`）に付与**します。
# MAGIC 個人のメールアドレスを1件ずつ指定するのではなく、**グループ単位で権限を管理**するのが
# MAGIC 実運用のやり方です（異動・入退社でも付け替えが不要）。
# MAGIC
# MAGIC 1. **付与前**: 隣の人にあなたのスキーマを読んでもらう → **エラー**になります
# MAGIC 2. **付与**: 下のセルを実行（グループに `USE SCHEMA` + `SELECT` を付与）
# MAGIC 3. **付与後**: もう一度読んでもらう → **読めるようになります**
# MAGIC 4. **REVOKE**: 取り消すと、また読めなくなります
# MAGIC
# MAGIC > 💡 グループには**あなた自身も含まれています**。「自分にも付与されている」状態ですが、
# MAGIC > あなたは元々 owner なので見え方は変わりません。**変化が起きるのは他の参加者側**です。
# MAGIC >
# MAGIC > 💡 `USE CATALOG` は**管理者が既にグループに付与済み**なので、ここでは不要です
# MAGIC > （このハンズオンで参加者がカタログレベルの権限を触ることはありません）。

# COMMAND ----------

def run_sql(stmt: str, label: str = ""):
    """実行して結果を分かりやすく表示する（失敗しても止めない）"""
    try:
        spark.sql(stmt)
        print(f"✓ {label or stmt}")
    except Exception as e:
        print(f"⚠️ {label or stmt}\n   → {str(e).splitlines()[0][:150]}")


G = f"`{PARTICIPANT_GROUP}`"

# グループが見えているか先に確認（見えない場合は付与が失敗するので理由を出す）
try:
    if not spark.sql(f"SHOW GROUPS LIKE '{PARTICIPANT_GROUP}'").collect():
        print(f"⚠️ グループ '{PARTICIPANT_GROUP}' がこのワークスペースから見えません。")
        print("   管理者に次を確認してください:")
        print("     ・Account Console でグループを作成したか")
        print("     ・そのグループを このワークスペース に追加したか")
        print("       （Settings → Identity and access → Groups → Add group）")
        print("   → 以下の付与は失敗しますが、実行される SQL は出力されるので流れは追えます。\n")
except Exception:
    pass

print(f"■ 参加者グループ {PARTICIPANT_GROUP} に customer の参照権限を付与します\n")

# 階層をたどって付与（上位の USE が無いと下位は見えない）
# USE CATALOG は管理者がグループに付与済みなので、ここではスキーマから
run_sql(f"GRANT USE SCHEMA ON SCHEMA {FQ} TO {G}", f"USE SCHEMA on {FQ}")
run_sql(f"GRANT SELECT ON TABLE {FQ}.customer TO {G}", f"SELECT on {FQ}.customer")

print("\n→ 隣の人に、次の SQL を実行してもらってください:")
print(f"   SELECT count(*) FROM {FQ}.customer;")
print("   （このセルの実行前はエラー、実行後は成功するはずです）")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 付与された権限を確認する
# MAGIC
# MAGIC `SHOW GRANTS` で「誰に何を許可しているか」が一覧できます。

# COMMAND ----------

print("■ customer テーブルの権限")
display(spark.sql(f"SHOW GRANTS ON TABLE {FQ}.customer"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### スキーマ単位でまとめて付与する（継承の効果）
# MAGIC
# MAGIC テーブルを 1 つずつ付与するのは大変です。**スキーマに付与すると配下すべてに効きます**。

# COMMAND ----------

run_sql(f"GRANT SELECT ON SCHEMA {FQ} TO {G}",
        f"SELECT on SCHEMA {FQ}（配下の全テーブルに継承）")
print("\n→ 隣の人は orders / lineitem など、他のテーブルも読めるようになります")
print("  （テーブル単位で付与していないのに読めるのが「継承」です）")

# COMMAND ----------

# MAGIC %md
# MAGIC ### REVOKE で権限を取り消す
# MAGIC
# MAGIC 付けた権限は `REVOKE` で外せます。**取り消すと相手は読めなくなります**。

# COMMAND ----------

run_sql(f"REVOKE SELECT ON SCHEMA {FQ} FROM {G}", f"REVOKE SELECT on SCHEMA {FQ}")
run_sql(f"REVOKE SELECT ON TABLE {FQ}.customer FROM {G}",
        f"REVOKE SELECT on {FQ}.customer")
print("\n→ 隣の人が再度 SELECT すると、今度は権限エラーになります")
print("  （USE SCHEMA は残っていますが、SELECT が無いので読めません）")
print("\n💡 グループから外すだけでも同じ効果です。")
print("   実運用では「権限を1件ずつ REVOKE」ではなく")
print("   「グループのメンバーシップを変える」ことで制御します。")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🖱️ UI でも同じことができます（Catalog Explorer）
# MAGIC
# MAGIC 1. **Catalog** → 自分のスキーマ → `customer` テーブル → **Permissions** タブ
# MAGIC 2. **Grant** ボタンをクリック
# MAGIC 3. **Principals** で**グループ**を選択（個人ユーザーも選べますが、グループ推奨）
# MAGIC 4. **Privileges** で `SELECT` にチェック → **Grant**
# MAGIC 5. 一覧に表示された行の **Revoke** で取り消せます
# MAGIC
# MAGIC スキーマ・カタログの **Permissions** タブでも同様に付与でき、**下位に継承**されます。
# MAGIC
# MAGIC 💡 **なぜグループに付与するのか**: 個人に直接付与すると、異動・入退社のたびに
# MAGIC すべてのオブジェクトを洗い出して付け替える必要があります。グループに付与しておけば、
# MAGIC **メンバーシップを変えるだけ**で権限が切り替わります。
# MAGIC 「誰が何を見られるか」の棚卸しもグループ単位で追えるようになります。
# MAGIC
# MAGIC 💡 **RBAC の限界**: この方式は明示的で分かりやすい反面、
# MAGIC 「機微な列だけ隠したい」「テーブルが 100 個に増えた」という場面では
# MAGIC **付与作業が爆発**します。そこで次の **ABAC** が役立ちます。

# COMMAND ----------

# MAGIC %md
# MAGIC # 【ABAC パート】
# MAGIC
# MAGIC ここからは **ABAC（属性ベースアクセス制御）** です。
# MAGIC **タグという「属性」を付け、タグに対してルールを 1 本張る**ことで、
# MAGIC 対象が増えても書き換え不要な制御を実現します。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 管理タグ（Governed Tag）— 全員で共有して使います
# MAGIC
# MAGIC ABAC の起点は **管理タグ（Governed Tag）** です。このハンズオンでは **3 種類**を使い、
# MAGIC **分類にもアクセス制御にも同じタグを使い回します**。
# MAGIC
# MAGIC | タグキー | 許可値 | 用途 |
# MAGIC |---|---|---|
# MAGIC | `uc_handson_sensitivity` | `confidential` / `internal` / `public` | **列マスクの対象**を決める（機微度） |
# MAGIC | `uc_handson_domain` | `procurement` / `sales` | **行フィルタの判定列**＋業務ドメインでの分類 |
# MAGIC | `uc_handson_layer` | `master` / `transaction` / `analytics` | データ層での分類（`05` の探索で使用） |
# MAGIC
# MAGIC ### 🧑‍🤝‍🧑 管理タグは組織で共有する資産です
# MAGIC
# MAGIC 管理タグは**アカウント全体で 1 つ**の定義を持ちます。個人ごとに作るものではなく、
# MAGIC **組織で「このタグを使う」と決めて全員で共有する**のが本来の使い方です。
# MAGIC （まさにそれが、表記ゆれを防ぎ、タグを起点に一括で保護できる理由です）
# MAGIC
# MAGIC そのため本ハンズオンでは、上記 3 種を**管理者が事前に作成**しています。
# MAGIC 下のセルは**確認のために実行**します。
# MAGIC
# MAGIC ```
# MAGIC   ✓ 管理タグは既に存在します（管理者が作成済み）: uc_handson_sensitivity — そのまま使えます
# MAGIC ```
# MAGIC
# MAGIC ↑ このように表示されるのが**正常**です。参加者全員が同じタグを使い、
# MAGIC **付与先（自分のテーブル・列）とポリシーは各自のスキーマ**なので、お互いの作業には影響しません。
# MAGIC
# MAGIC > 💡 タグ定義が共有され、付与とポリシーは個別 — この分離が ABAC の設計思想です。
# MAGIC >
# MAGIC > `CREATE GOVERNED TAG` は `IF NOT EXISTS` 非対応 / `DESCRIPTION` と `VALUES` を使用
# MAGIC > （`COMMENT` / `ALLOWED VALUES` ではありません）。

# COMMAND ----------

# 管理タグはアカウント共有リソース。管理者が事前に作成しているため、通常は
# ALREADY_EXISTS になる（それが正常）。未作成の環境でも動くよう作成も試みる。
governed_tags = [
    "CREATE GOVERNED TAG uc_handson_sensitivity "
    "DESCRIPTION '機微度（列マスクの対象を決める）' "
    "VALUES ('confidential','internal','public')",
    "CREATE GOVERNED TAG uc_handson_domain "
    "DESCRIPTION '業務ドメイン（行フィルタの判定にも使用）' "
    "VALUES ('procurement','sales')",
    "CREATE GOVERNED TAG uc_handson_layer "
    "DESCRIPTION 'データ層（マスタ / トランザクション / 分析）' "
    "VALUES ('master','transaction','analytics')",
]
for stmt in governed_tags:
    tag_name = stmt.split()[3]
    try:
        spark.sql(stmt)
        print(f"✓ 管理タグを作成しました: {tag_name}（この環境では未作成でした）")
    except Exception as e:
        if "ALREADY_EXISTS" in str(e) or "already exists" in str(e).lower():
            print(f"✓ 管理タグは既に存在します（管理者が作成済み）: {tag_name} — そのまま使えます")
        else:
            print(f"⚠️ {tag_name}: {str(e).splitlines()[0][:120]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🖱️ UI で管理タグを確認する（Catalog Explorer）
# MAGIC
# MAGIC 共有されている管理タグを画面で見てみましょう。
# MAGIC
# MAGIC 1. 左メニュー **Catalog** を開く
# MAGIC 2. 上部の **Govern**（盾アイコン）をクリック
# MAGIC 3. ドロップダウンから **Governed Tags** を選択
# MAGIC 4. `uc_handson_sensitivity` などをクリック
# MAGIC    → **許可値**と、**どこで使われているか（利用状況）** が確認できます
# MAGIC
# MAGIC 組織でタグを管理する立場なら、この画面が起点になります。
# MAGIC 新しく作る場合は **Create governed tag** から
# MAGIC （**Tag key** / 任意の **Description** / **Allowed values** を入力 → **Create**）。
# MAGIC
# MAGIC > 🔑 **作成できるのは**: アカウント管理者、ワークスペース管理者、
# MAGIC > または `CREATE` 権限を付与されたユーザー。
# MAGIC > 管理タグは**アカウント全体**に効くため、組織横断のタグ統制をここで一元管理します。
# MAGIC > タグを**付与する**（`ASSIGN`）権限は別で、管理者から付与されます。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. タグの「許可値」で統制する（Tag Policies）
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
# MAGIC `uc_handson_sensitivity` には `confidential` / `internal` / `public` のみ許可しました。
# MAGIC **許可していない値を入れようとすると、実際にエラーになります** — 下のセルで体験してみましょう。

# COMMAND ----------

# 許可値の外側の値を入れてみる → 弾かれることを確認（これが Tag Policy の効果）
try:
    spark.sql(
        "ALTER TABLE customer ALTER COLUMN c_acctbal "
        "SET TAGS ('uc_handson_sensitivity' = 'ちょっと秘密')"
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
# MAGIC ## 5. テーブル・列にタグを付与
# MAGIC
# MAGIC 定義したタグを実際に付けます。**この時点ではまだデータの見え方は変わりません**
# MAGIC （タグは「印」であり、ポリシーを張って初めて制御が効きます）。
# MAGIC
# MAGIC **テーブルレベル**（業務ドメイン・データ層での分類 → `05` の探索で活用）
# MAGIC
# MAGIC | テーブル | domain | layer |
# MAGIC |---|---|---|
# MAGIC | `part` / `supplier` | `procurement` | `master` |
# MAGIC | `customer` | `sales` | `master` |
# MAGIC | `orders` / `lineitem` | `sales` | `transaction` |
# MAGIC
# MAGIC **列レベル**（アクセス制御の対象を指定 → `6` `7` で活用）
# MAGIC
# MAGIC | 列 | タグ | 使われ方 |
# MAGIC |---|---|---|
# MAGIC | `customer.c_acctbal`（口座残高） | `uc_handson_sensitivity = confidential` | **列マスクの対象**になる |
# MAGIC | `supplier.s_acctbal`（口座残高） | `uc_handson_sensitivity = confidential` | 同上（ポリシー追加なしで効く） |
# MAGIC | `customer.c_mktsegment`（市場セグメント） | `uc_handson_domain = sales` | **行フィルタの判定列**になる |

# COMMAND ----------

# テーブルレベルのタグ（分類用）
table_tags = [
    "ALTER TABLE part     SET TAGS ('uc_handson_domain' = 'procurement', 'uc_handson_layer' = 'master')",
    "ALTER TABLE supplier SET TAGS ('uc_handson_domain' = 'procurement', 'uc_handson_layer' = 'master')",
    "ALTER TABLE customer SET TAGS ('uc_handson_domain' = 'sales',       'uc_handson_layer' = 'master')",
    "ALTER TABLE orders   SET TAGS ('uc_handson_domain' = 'sales',       'uc_handson_layer' = 'transaction')",
    "ALTER TABLE lineitem SET TAGS ('uc_handson_domain' = 'sales',       'uc_handson_layer' = 'transaction')",
]
for stmt in table_tags:
    target = stmt.split("SET TAGS")[0].replace("ALTER TABLE", "").strip()
    try:
        spark.sql(stmt)
        print(f"✓ {target}")
    except Exception as e:
        msg = str(e)
        if "not an allowed value for tag policy key" in msg:
            print(f"⚠️ {target}: 許可値に無い値です →")
            print("   ", msg[msg.find("Tag value"):].splitlines()[0][:200])
        else:
            print(f"· skip: {target}: {msg.splitlines()[0][:110]}")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 列レベル: 機微な列に「機微度」タグを付ける（→ 6 の列マスクの対象になる）
# MAGIC ALTER TABLE customer ALTER COLUMN c_acctbal SET TAGS ('uc_handson_sensitivity' = 'confidential');

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 別テーブルの同種の列にも同じタグ（→ ポリシーを増やさず保護が広がることを 6 で確認）
# MAGIC ALTER TABLE supplier ALTER COLUMN s_acctbal SET TAGS ('uc_handson_sensitivity' = 'confidential');

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 列レベル: 行フィルタの判定に使う列（→ 7 の行フィルタで参照される）
# MAGIC ALTER TABLE customer ALTER COLUMN c_mktsegment SET TAGS ('uc_handson_domain' = 'sales');

# COMMAND ----------

# 付与されたタグを確認（テーブル・列の両方）
print("■ テーブルレベルのタグ")
display(spark.sql(f"""
  SELECT table_name, tag_name, tag_value
  FROM system.information_schema.table_tags
  WHERE catalog_name = '{catalog}' AND schema_name = '{schema}'
  ORDER BY table_name, tag_name
"""))

# COMMAND ----------

print("■ 列レベルのタグ")
display(spark.sql(f"""
  SELECT table_name, column_name, tag_name, tag_value
  FROM system.information_schema.column_tags
  WHERE catalog_name = '{catalog}' AND schema_name = '{schema}'
  ORDER BY table_name, column_name
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🖱️ UI でタグを付ける（管理タグは選択式になります）
# MAGIC
# MAGIC 1. `orders` テーブルの **Overview** タブ右側 **Tags** の **＋ Add tags**（既にある場合は ✏️）
# MAGIC 2. **Key** のドロップダウンを開く → **Governed** セクションに 🔒 付きで
# MAGIC    `uc_handson_domain` / `uc_handson_layer` / `uc_handson_sensitivity` が並びます
# MAGIC 3. キーを選ぶと **Value も許可値から選択**できます（自由入力ではありません）
# MAGIC 4. **Add** → **Save**
# MAGIC 5. 列のタグは、列一覧の右端 **⋮ → Edit tags** から同様に付与
# MAGIC
# MAGIC > 💡 これが管理タグの利点です。**選択式なので表記ゆれが起きません**。
# MAGIC > 通常タグ（`CREATE GOVERNED TAG` していないキー）は **Other** セクションに出ます。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. タグ駆動の列マスク（ABAC COLUMN MASK ポリシー）
# MAGIC
# MAGIC マスク関数を定義し、**`uc_handson_sensitivity = confidential` タグを持つ列すべて**にポリシーを1本張ります。
# MAGIC `MATCH COLUMNS` がタグ条件、`ON COLUMN` がマッチした列を指します。
# MAGIC 管理者（`admins` / `data_governance_admins`）は実値、それ以外は `NULL` にマスクされます。

# COMMAND ----------

# MAGIC %sql
# MAGIC -- マスク関数（管理者は実値、それ以外は NULL）
# MAGIC CREATE OR REPLACE FUNCTION mask_confidential_value(v DECIMAL(18,2))
# MAGIC RETURN CASE
# MAGIC   WHEN is_account_group_member('admins')
# MAGIC     OR is_account_group_member('data_governance_admins') THEN v
# MAGIC   ELSE NULL
# MAGIC END;

# COMMAND ----------

# スキーマ配下で「uc_handson_sensitivity=confidential タグの付いた列」に自動でマスクを適用
# ※ ON SCHEMA は修飾名を直書き（IDENTIFIER 不可）。f-string で FQ を埋め込む。
spark.sql(f"""
  CREATE OR REPLACE POLICY mask_confidential_columns
  ON SCHEMA {FQ}
  COMMENT 'uc_handson_sensitivity=confidential のタグが付いた列を、管理者以外にはマスクする'
  COLUMN MASK mask_confidential_value
  TO `account users`
  FOR TABLES
  MATCH COLUMNS has_tag_value('uc_handson_sensitivity', 'confidential') AS c
  ON COLUMN c
""")
print("✓ policy mask_confidential_columns created")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 効果確認: 非 admin なら c_acctbal が NULL に、admin なら実値
# MAGIC SELECT c_custkey, c_name, c_mktsegment, c_acctbal
# MAGIC FROM customer LIMIT 10;

# COMMAND ----------

# MAGIC %md
# MAGIC 💡 **ABAC の威力**: 同じタグ `uc_handson_sensitivity=confidential` を別テーブルの列（例 `supplier.s_acctbal`）に
# MAGIC 付けると、**新しいポリシーを書かずに**その列も自動的にマスクされます。試しに下を実行して確認できます
# MAGIC （後片付けで戻します）。

# COMMAND ----------

# MAGIC %sql
# MAGIC -- （任意）supplier の残高列にも同じタグ → 同一ポリシーが自動適用される
# MAGIC ALTER TABLE supplier ALTER COLUMN s_acctbal SET TAGS ('uc_handson_sensitivity' = 'confidential');

# COMMAND ----------

# MAGIC %sql
# MAGIC -- supplier.s_acctbal も（非 admin なら）NULL にマスクされている＝ポリシー追加不要
# MAGIC SELECT s_suppkey, s_name, s_acctbal FROM supplier LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. タグ駆動の行フィルタ（ABAC ROW FILTER ポリシー）
# MAGIC
# MAGIC 「営業は担当する市場セグメントの顧客のみ閲覧」を **行フィルタ関数 + タグ駆動ポリシー** で実現します。
# MAGIC `uc_handson_domain` タグの付いた列（＝ `c_mktsegment`）をフィルタ関数の引数に渡します。
# MAGIC 管理者は全件、営業は所属グループのセグメントのみ、どちらでもなければ 0 件になります。

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 行フィルタ関数: 管理者は全件、それ以外はセグメント別グループに応じて限定
# MAGIC CREATE OR REPLACE FUNCTION row_filter_by_market_segment(segment STRING)
# MAGIC RETURN
# MAGIC   is_account_group_member('admins')
# MAGIC   OR is_account_group_member('data_governance_admins')
# MAGIC   OR (segment = 'AUTOMOBILE' AND is_account_group_member('sales_automobile'))
# MAGIC   OR (segment = 'BUILDING'   AND is_account_group_member('sales_building'))
# MAGIC   OR (segment = 'MACHINERY'  AND is_account_group_member('sales_machinery'));

# COMMAND ----------

# スキーマ配下で「uc_handson_domain タグの付いた列」を引数に行フィルタを自動適用
spark.sql(f"""
  CREATE OR REPLACE POLICY filter_rows_by_domain
  ON SCHEMA {FQ}
  COMMENT 'uc_handson_domain タグが付いた列で、担当セグメントの行のみに絞り込む'
  ROW FILTER row_filter_by_market_segment
  TO `account users`
  FOR TABLES
  MATCH COLUMNS has_tag_value('uc_handson_domain', 'sales') AS seg
  USING COLUMNS (seg)
""")
print("✓ policy filter_rows_by_domain created")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 効果確認: 管理者なら全セグメント、非該当グループなら 0 件
# MAGIC SELECT c_mktsegment, count(*) AS n
# MAGIC FROM customer GROUP BY c_mktsegment ORDER BY c_mktsegment;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. 適用中のポリシー一覧
# MAGIC
# MAGIC スキーマに張られている ABAC ポリシーを確認します。

# COMMAND ----------

display(spark.sql(f"SHOW POLICIES ON SCHEMA {FQ}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. 後片付け（⚠️ 必ず実行してから 04 へ進む）
# MAGIC
# MAGIC **重要**: 行フィルタ/列マスクポリシーを張ったまま次の `04_lineage` に進むと、実行者が対象グループに
# MAGIC 属していない場合 `customer` が **0 行 / c_acctbal が NULL** に見え、
# MAGIC **04 の JOIN 結果（order_analysis_summary）が空になります**。
# MAGIC ここでポリシーと列タグを外し、素の状態（750,000 行・実値）に戻します。
# MAGIC （マスク関数 `mask_confidential_value` / フィルタ関数 `row_filter_by_market_segment`、管理タグ定義は残るので再適用はいつでも可能）

# COMMAND ----------

# DROP POLICY は IF EXISTS 非対応のため try/except でラップ
for pol in ["mask_confidential_columns", "filter_rows_by_domain"]:
    try:
        spark.sql(f"DROP POLICY {pol} ON SCHEMA {FQ}")
        print("✓ dropped policy:", pol)
    except Exception as e:
        print("· skip:", str(e).splitlines()[0][:90])

print()
print("※ タグ自体は外しません（ポリシーを外せば制御は解除されます）。")
print("  タグは 05_discovery の「タグで探す」でそのまま使うので残しておきます。")

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
# MAGIC 2. 右端 **⋮ → Edit tags**（またはタグ列の＋）→ 管理タグ `uc_handson_sensitivity` を選び 値 `confidential` → 保存
# MAGIC 3. 管理タグ自体の作成/許可値の管理は **Catalog Explorer 左下の「Tags」**（または Account 管理）から
# MAGIC
# MAGIC **C. ABAC ポリシーを UI で作る（本ノートブック冒頭のスクショの画面）**
# MAGIC 1. **Catalog** → 対象カタログ/スキーマ → **Policies**（ポリシー）タブ → **Create policy / 新しいポリシー**
# MAGIC 2. **ポリシーの種類**: 「列マスク」または「行フィルター」を選択
# MAGIC 3. **プリンシパルとスコープ**:
# MAGIC    - 適用対象（TO）に `account users`（＝全員に適用）、除外（EXCEPT）に管理者グループ、を指定できる
# MAGIC      ※ ここでの `TO` は「**ポリシーを適用する対象**」で、権限付与の `GRANT ... TO` とは別物です
# MAGIC    - **範囲（ON）**: カタログ / スキーマ / テーブルを選択（ここでスキーマを選ぶと配下に自動適用）
# MAGIC 4. **タグ条件（MATCH COLUMNS）**: `uc_handson_sensitivity = confidential` のようにタグで対象列を絞り込む
# MAGIC 5. 参照する関数（`mask_confidential_value` / `row_filter_by_market_segment`）を選択 → **ポリシーを作成**
# MAGIC    （右ペインの「コードを表示」で、UI 操作と等価な SQL がリアルタイムに確認できる）
# MAGIC
# MAGIC **D. 効果の確認方法**
# MAGIC - 別ユーザー（各グループ所属）でログインし `SELECT * FROM customer` → 行数・`c_acctbal` の見え方の差を確認
# MAGIC - 管理者は全件・実値、非該当グループは絞り込み・NULL になる
# MAGIC - **ABAC の要点**: タグを別テーブル/別列に付け替えるだけで、ポリシーを増やさず保護範囲が変わる
# MAGIC
# MAGIC 次は **`04_lineage`** で、テーブル間のデータリネージを生成・可視化します。
