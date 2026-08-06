# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — メタデータ設計（説明文と制約）
# MAGIC
# MAGIC > 🔑 **必要な権限**: 自分のスキーマの owner（追加付与は不要）
# MAGIC
# MAGIC ガバナンスの土台として、テーブル/カラムに **COMMENT（説明文）** と
# MAGIC **主キー/外部キー制約** を付与します。これにより以下が向上します。
# MAGIC
# MAGIC - **データ探索（Discovery）**: 検索・カタログ理解が容易に（`05`）
# MAGIC - **リネージ**: PK/FK 宣言で関係が明確に（`04`）
# MAGIC - **Genie**: メタデータ・制約から自然言語クエリの精度が上がる（`08`）
# MAGIC
# MAGIC 対象は `01_ingest_data` で取り込んだ TPC-H（部品調達・受注）テーブル群です。
# MAGIC
# MAGIC > 💡 **タグは `03_access_control` で扱います**。タグはアクセス制御（ABAC）と
# MAGIC > 一体で設計するものなので、まとめて 1 箇所で学ぶ構成にしています。
# MAGIC
# MAGIC > 📖 [テーブル/カラムのコメント](https://docs.databricks.com/ja/data-governance/unity-catalog/index.html) ／
# MAGIC > [主キー・外部キー制約](https://docs.databricks.com/ja/tables/constraints.html)

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# _config が catalog / schema / FQ を定義し、USE CATALOG / USE SCHEMA まで実行済み
print(f"target = {FQ}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## テーブル COMMENT

# COMMAND ----------

table_comments = {
    "region": "地域マスタ（5 地域）",
    "nation": "国マスタ（region への外部キー）",
    "supplier": "サプライヤーマスタ（部品供給元）",
    "part": "部品マスタ（製造・調達対象の部品）",
    "customer": "顧客マスタ（市場セグメント別）",
    "orders": "受注ヘッダ（顧客ごとの注文）",
    "lineitem": "受注明細（部品・サプライヤー・数量・価格）",
}
for t, c in table_comments.items():
    spark.sql(f"COMMENT ON TABLE {FQ}.{t} IS '{c}'")
    print(f"✓ COMMENT ON {t}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## カラム COMMENT（主要カラム）

# COMMAND ----------

col_comments = [
    ("orders", "o_orderkey", "受注の一意 ID"),
    ("orders", "o_custkey", "顧客 ID（customer.c_custkey への外部キー）"),
    ("orders", "o_totalprice", "受注合計金額"),
    ("orders", "o_orderstatus", "受注ステータス: O=未完了 / F=完了 / P=処理中"),
    ("lineitem", "l_orderkey", "受注 ID（orders.o_orderkey への外部キー）"),
    ("lineitem", "l_partkey", "部品 ID（part.p_partkey への外部キー）"),
    ("lineitem", "l_suppkey", "サプライヤー ID（supplier.s_suppkey への外部キー）"),
    ("lineitem", "l_quantity", "発注数量"),
    ("lineitem", "l_discount", "割引率（0.0〜0.10）"),
    ("customer", "c_mktsegment", "市場セグメント: AUTOMOBILE / BUILDING / MACHINERY 等"),
    ("customer", "c_acctbal", "口座残高（与信の参考。機微情報）"),
    ("supplier", "s_acctbal", "サプライヤー口座残高（機微情報）"),
]
for tbl, col, cmt in col_comments:
    spark.sql(f"ALTER TABLE {FQ}.{tbl} ALTER COLUMN {col} COMMENT '{cmt}'")
    print(f"✓ {tbl}.{col}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 主キー / 外部キー制約
# MAGIC
# MAGIC UC の PK/FK は **RELY 情報用**（強制はされない）ですが、リネージ・Genie・クエリ最適化のヒントになります。
# MAGIC PK 列は NOT NULL である必要があるため、先に制約を付けます。

# COMMAND ----------

not_null = [
    "ALTER TABLE region   ALTER COLUMN r_regionkey SET NOT NULL",
    "ALTER TABLE nation   ALTER COLUMN n_nationkey SET NOT NULL",
    "ALTER TABLE supplier ALTER COLUMN s_suppkey   SET NOT NULL",
    "ALTER TABLE part     ALTER COLUMN p_partkey   SET NOT NULL",
    "ALTER TABLE customer ALTER COLUMN c_custkey   SET NOT NULL",
    "ALTER TABLE orders   ALTER COLUMN o_orderkey  SET NOT NULL",
    "ALTER TABLE lineitem ALTER COLUMN l_orderkey  SET NOT NULL",
    "ALTER TABLE lineitem ALTER COLUMN l_linenumber SET NOT NULL",
]
for stmt in not_null:
    try:
        spark.sql(stmt); print("✓ " + stmt.split("ALTER TABLE")[1].split("ALTER COLUMN")[0].strip())
    except Exception as e:
        print("· skip:", str(e).splitlines()[0][:80])

# COMMAND ----------

pk_fk = [
    "ALTER TABLE region   ADD CONSTRAINT pk_region   PRIMARY KEY (r_regionkey)",
    "ALTER TABLE nation   ADD CONSTRAINT pk_nation   PRIMARY KEY (n_nationkey)",
    "ALTER TABLE supplier ADD CONSTRAINT pk_supplier PRIMARY KEY (s_suppkey)",
    "ALTER TABLE part     ADD CONSTRAINT pk_part     PRIMARY KEY (p_partkey)",
    "ALTER TABLE customer ADD CONSTRAINT pk_customer PRIMARY KEY (c_custkey)",
    "ALTER TABLE orders   ADD CONSTRAINT pk_orders   PRIMARY KEY (o_orderkey)",
    "ALTER TABLE lineitem ADD CONSTRAINT pk_lineitem PRIMARY KEY (l_orderkey, l_linenumber)",
    "ALTER TABLE nation   ADD CONSTRAINT fk_nation_region   FOREIGN KEY (n_regionkey) REFERENCES region(r_regionkey)",
    "ALTER TABLE customer ADD CONSTRAINT fk_customer_nation FOREIGN KEY (c_nationkey) REFERENCES nation(n_nationkey)",
    "ALTER TABLE supplier ADD CONSTRAINT fk_supplier_nation FOREIGN KEY (s_nationkey) REFERENCES nation(n_nationkey)",
    "ALTER TABLE orders   ADD CONSTRAINT fk_orders_customer FOREIGN KEY (o_custkey) REFERENCES customer(c_custkey)",
    "ALTER TABLE lineitem ADD CONSTRAINT fk_lineitem_orders   FOREIGN KEY (l_orderkey) REFERENCES orders(o_orderkey)",
    "ALTER TABLE lineitem ADD CONSTRAINT fk_lineitem_part     FOREIGN KEY (l_partkey)  REFERENCES part(p_partkey)",
    "ALTER TABLE lineitem ADD CONSTRAINT fk_lineitem_supplier FOREIGN KEY (l_suppkey)  REFERENCES supplier(s_suppkey)",
]
for stmt in pk_fk:
    try:
        spark.sql(stmt); print("✓ " + stmt.split("ADD CONSTRAINT")[1].split()[0])
    except Exception as e:
        print("· skip:", str(e).splitlines()[0][:80])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 確認

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE TABLE EXTENDED orders

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で設定する手順（Catalog Explorer）
# MAGIC
# MAGIC 上のセルは SQL で一括設定しましたが、同じことを **Catalog Explorer の画面から個別に設定** できます。
# MAGIC ハンズオンでは 1 テーブルだけ UI で操作して体験してください。
# MAGIC
# MAGIC **A. テーブル/カラムのコメントを UI で付ける**
# MAGIC 1. 左メニュー **Catalog** → 対象カタログ → スキーマ → `orders` テーブルをクリック
# MAGIC 2. **Overview** タブでテーブル名の下の説明欄（"Add comment"）をクリック → コメントを入力して保存
# MAGIC 3. カラム一覧で各カラムの **Comment** 列をクリック → インライン編集で保存
# MAGIC
# MAGIC **A-2. ⭐ AI にコメントを書かせる（AI 生成コメント）**
# MAGIC
# MAGIC 説明文をゼロから書くのは大変です。**AI がテーブル/列の内容を読んで候補を提案**してくれます。
# MAGIC
# MAGIC *テーブルのコメント*
# MAGIC 1. **Catalog** → 対象テーブル（`part` など、まだコメントが無いものが分かりやすい）を開く
# MAGIC 2. **Overview** タブの右ペインにある **AI Suggested Comment** で **AI generate** をクリック
# MAGIC 3. 生成された案を **Accept**（採用）または **Edit**（編集して保存）
# MAGIC
# MAGIC *列のコメント（まとめて生成）*
# MAGIC 1. 同じテーブルの列一覧の上にある **AI generate** をクリック
# MAGIC 2. 列ごとにコメント候補が生成される
# MAGIC 3. 良いものは **チェックマーク** で確定（不要なものは採用しない）
# MAGIC
# MAGIC > 📖 [AI 生成コメント](https://learn.microsoft.com/ja-jp/azure/databricks/comments/ai-comments)
# MAGIC >
# MAGIC > **前提**: ワークスペースで AI 支援機能（AI-assistive features）が有効であること。
# MAGIC > **権限**: 対象オブジェクトの owner または `MODIFY`（view / materialized view は owner のみ）。
# MAGIC >
# MAGIC > 💡 **なぜ重要か**: ドキュメント整備は「やるべきだが手が回らない」典型です。
# MAGIC > AI が下書きを作り、人間はレビューするだけにすると、**メタデータ整備のコストが劇的に下がります**。
# MAGIC > そしてここで整えた説明文が、後の `05`（探索）と `08`（Genie の精度）に直結します。
# MAGIC >
# MAGIC > ⚠️ AI の提案は**必ず内容を確認**してから採用してください（誤った説明が付くと逆効果）。
# MAGIC
# MAGIC **B. 主キー/外部キーの確認**
# MAGIC - PK/FK は SQL（`ALTER TABLE ... ADD CONSTRAINT`）での宣言が基本です。
# MAGIC   UI では **Details** タブや **Entity Relationship**（ER 図）で宣言済みの関係を確認できます。
# MAGIC
# MAGIC これで**メタデータの記述**は完了です（00 → 01 → 02）。
# MAGIC
# MAGIC 次の **`03_access_control`** では、
# MAGIC **アクセス制御（RBAC → タグ設計 → ABAC）** を体験します。
# MAGIC タグはアクセス制御と一体で扱うため、`03` にまとめてあります。
