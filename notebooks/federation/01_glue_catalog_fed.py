# Databricks notebook source
# MAGIC %md
# MAGIC > ## 📎 参考実装 — ハンズオン対象外
# MAGIC >
# MAGIC > このノートブックは **Lakehouse Federation** の参考実装です。
# MAGIC > **ハンズオンでは実行しません**（AWS 側のリソース構築が前提で、環境準備に時間とコストがかかるため）。
# MAGIC > ハンズオンで手を動かすのは `notebooks/core/` の 00〜08 です。
# MAGIC >
# MAGIC > 自分の AWS 環境で試す場合は、先に `terraform/` で環境を構築してください。

# COMMAND ----------

# MAGIC %md
# MAGIC # 01 — Catalog Federation: AWS Glue
# MAGIC
# MAGIC AWS Glue Data Catalog のテーブルを Unity Catalog 経由で透過的に参照します。
# MAGIC Databricks は Glue のメタデータを取得し、**S3 上のデータを直接読み取り**（Spark エンジンで処理）します。
# MAGIC
# MAGIC Glue 側の工場マスタ（`terraform/` が投入）:
# MAGIC
# MAGIC | テーブル | フォーマット | 内容 |
# MAGIC |---|---|---|
# MAGIC | `sensors` | Parquet | センサーマスタ |
# MAGIC | `machines` | Delta | 機械マスタ（machine_name / production_line / factory / status） |
# MAGIC | `quality_inspections` | Iceberg | 品質検査（result: pass/fail/warning） |
# MAGIC
# MAGIC > 3 つの異なる **オープンテーブルフォーマット**（Parquet / Delta / Iceberg）を透過的に扱える点がポイント。
# MAGIC >
# MAGIC > 📖 [AWS Glue Catalog Federation](https://docs.databricks.com/ja/query-federation/hive-metastore.html)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## ⚠️ 前提（このノートブックを実行する前に完了しているべきこと）
# MAGIC
# MAGIC Glue の Catalog Federation は、**S3 データへのアクセス許可まで含めた一連の登録**が済んで初めて機能します。
# MAGIC 未登録だと、後続の `SELECT` は「S3 にアクセスできない」等で失敗します。
# MAGIC
# MAGIC | # | 登録物 | 役割 |
# MAGIC |---|---|---|
# MAGIC | 1 | **IAM ロール**（Glue 読取 / S3 読取） | Databricks が Glue メタデータ + S3 データにアクセスする権限 |
# MAGIC | 2 | **Service Credential** | Glue API 用の UC 資格情報 |
# MAGIC | 3 | **Storage Credential** | S3 データ読取用の UC 資格情報 |
# MAGIC | 4 | **External Location** | S3 パスへのアクセスをガバナンス（**これが無いと S3 のデータ本体を読めない**） |
# MAGIC | 5 | **Connection**（GLUE） | Glue への接続定義 |
# MAGIC | 6 | **Foreign Catalog** | Glue を UC のカタログとしてミラーリング |
# MAGIC
# MAGIC 👉 **本デモではこれらを `terraform/` で一括構築済み**の前提です（`00_prereq_env` 参照）。
# MAGIC Terraform を使わず手動で作る場合の UI 手順も `00_prereq_env` に記載しています。
# MAGIC このノートブックは「登録済みの Glue foreign catalog を**使う**」ところから始めます。

# COMMAND ----------

dbutils.widgets.text("fed_catalog_glue", "", "Glue foreign catalog 名")
glue_cat = dbutils.widgets.get("fed_catalog_glue")
assert glue_cat, "fed_catalog_glue が未設定です（terraform output databricks_catalogs.glue）"

# --- 前提チェック: foreign catalog と external location が登録済みか ---
cat_names = {r[0] for r in spark.sql("SHOW CATALOGS").collect()}
assert glue_cat in cat_names, (
    f"Glue foreign catalog '{glue_cat}' が存在しません。"
    " 先に terraform apply（または 00_prereq_env の UI 手順）で "
    "Connection / External Location / Foreign Catalog を登録してください。"
)
# external location の存在も確認（S3 データ読取の前提）
try:
    ext_locs = [r[0] for r in spark.sql("SHOW EXTERNAL LOCATIONS").collect()]
    print(f"✓ external locations 登録数: {len(ext_locs)}")
except Exception as e:
    print("· external location の確認をスキップ:", str(e).splitlines()[0][:80])
print(f"✓ Glue foreign catalog '{glue_cat}' を確認")

# Glue の database 名は <db_prefix>_factory_master。foreign catalog 内では自動的にスキーマとして見える。
# ここでは SHOW SCHEMAS で実際の名前を発見してから使う。
schemas = [r[0] for r in spark.sql(f"SHOW SCHEMAS IN {glue_cat}").collect()]
master_schema = next((s for s in schemas if s.endswith("factory_master")), schemas[0] if schemas else None)
print("glue catalog :", glue_cat)
print("schemas      :", schemas)
print("master schema:", master_schema)

# COMMAND ----------

# MAGIC %md
# MAGIC ## テーブル一覧

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN {glue_cat}.{master_schema}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## センサーマスタ（Parquet）

# COMMAND ----------

display(spark.table(f"{glue_cat}.{master_schema}.sensors"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 機械マスタ（Delta）

# COMMAND ----------

display(spark.table(f"{glue_cat}.{master_schema}.machines"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 品質検査（Iceberg）— フォーマットを意識せず同じ SQL で参照できる

# COMMAND ----------

display(spark.table(f"{glue_cat}.{master_schema}.quality_inspections"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 集計例: 工場建屋別の機械台数（S3 上のデータを Spark が直接集計）

# COMMAND ----------

spark.sql(f"""
  SELECT factory, production_line, count(*) AS machines
  FROM {glue_cat}.{master_schema}.machines
  GROUP BY factory, production_line
  ORDER BY factory, production_line
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で確認する手順
# MAGIC
# MAGIC 1. **Catalog Explorer** で Glue foreign catalog を開く → スキーマ `*_factory_master` → 3 テーブル
# MAGIC 2. `machines` の **Details** で、フォーマットが Delta、ソースが Glue であることを確認
# MAGIC 3. `quality_inspections` は Iceberg だが、UI/SQL 上は同じテーブルとして扱える
# MAGIC 4. データは S3 のまま（コピーされていない）ことを External Location で確認
# MAGIC
# MAGIC 次は **`02_redshift_query_fed`** で Query Federation を見ます。
