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
# MAGIC # 02 — Query Federation: Amazon Redshift
# MAGIC
# MAGIC Amazon Redshift Serverless に **JDBC 経由**でクエリを発行します。
# MAGIC フィルタ・集約などは **Redshift 側にプッシュダウン**され、結果のみが Databricks に返却されます
# MAGIC （＝ Redshift の計算資源を活用、大きなデータを転送しない）。
# MAGIC
# MAGIC Redshift 側の工場トランザクション（`terraform/` が投入）:
# MAGIC
# MAGIC | テーブル | 内容 |
# MAGIC |---|---|
# MAGIC | `sensor_readings` | センサー測定値（status: normal/warning/critical） |
# MAGIC | `production_events` | 生産イベント（event_type: start/stop/maintenance/error/calibration） |
# MAGIC | `quality_inspections` | 品質検査 |
# MAGIC
# MAGIC > **Glue との対比**: Glue はメタデータ経由で S3 を Databricks が直接読む。Redshift はクエリを
# MAGIC > Redshift エンジンにプッシュダウンする。
# MAGIC >
# MAGIC > 📖 [Redshift への接続](https://docs.databricks.com/ja/query-federation/redshift.html)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## ⚠️ 前提
# MAGIC
# MAGIC Query Federation は S3 external location は不要ですが、**Connection（Redshift host/user/password）と
# MAGIC Foreign Catalog の登録**が前提です（本デモは `terraform/` で構築済み。手動時は `00_prereq_env` 参照）。
# MAGIC Glue（Catalog Federation）と違い S3 直接読取が無いぶん、登録物はシンプルです。

# COMMAND ----------

dbutils.widgets.text("fed_catalog_redshift", "", "Redshift foreign catalog 名")
rs_cat = dbutils.widgets.get("fed_catalog_redshift")
assert rs_cat, "fed_catalog_redshift が未設定です（terraform output databricks_catalogs.redshift）"

# --- 前提チェック: foreign catalog が登録済みか ---
cat_names = {r[0] for r in spark.sql("SHOW CATALOGS").collect()}
assert rs_cat in cat_names, (
    f"Redshift foreign catalog '{rs_cat}' が存在しません。"
    " 先に terraform apply（または 00_prereq_env の UI 手順）で Connection / Foreign Catalog を登録してください。"
)
print(f"✓ Redshift foreign catalog '{rs_cat}' を確認")

# Redshift の schema 名は db_prefix（terraform の source_schema）。SHOW SCHEMAS で発見。
# Redshift には catalog_history / pg_* など多数のシステムスキーマがあるため、
# 「期待テーブル sensor_readings を実際に含むスキーマ」を選ぶ（名前ベースの推測より確実）。
schemas = [r[0] for r in spark.sql(f"SHOW SCHEMAS IN {rs_cat}").collect()]
_SYS = {"information_schema", "public", "catalog_history"}
user_schemas = [s for s in schemas if s not in _SYS and not s.startswith("pg_")]

def _has_table(schema, tbl="sensor_readings"):
    try:
        tables = {r["tableName"] for r in spark.sql(f"SHOW TABLES IN {rs_cat}.{schema}").collect()}
        return tbl in tables
    except Exception:
        return False

rs_schema = next((s for s in user_schemas if _has_table(s)), (user_schemas[0] if user_schemas else "public"))
print("redshift catalog:", rs_cat)
print("schemas         :", schemas)
print("using schema    :", rs_schema)

# COMMAND ----------

# MAGIC %md
# MAGIC ## テーブル一覧

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN {rs_cat}.{rs_schema}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## センサー測定値

# COMMAND ----------

display(spark.table(f"{rs_cat}.{rs_schema}.sensor_readings"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## プッシュダウンの確認
# MAGIC
# MAGIC 集約クエリを実行し、`EXPLAIN FORMATTED` でスキャン/集約が Redshift 側に委譲されることを確認します。

# COMMAND ----------

spark.sql(f"""
  SELECT status, count(*) AS n, round(avg(value), 2) AS avg_value
  FROM {rs_cat}.{rs_schema}.sensor_readings
  GROUP BY status ORDER BY n DESC
""").display()

# COMMAND ----------

spark.sql(f"""
  EXPLAIN FORMATTED
  SELECT machine_id, count(*)
  FROM {rs_cat}.{rs_schema}.sensor_readings
  WHERE status = 'critical'
  GROUP BY machine_id
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 異常停止のダウンタイム（生産イベント）

# COMMAND ----------

spark.sql(f"""
  SELECT machine_id,
         sum(CASE WHEN event_type = 'maintenance' THEN duration_minutes ELSE 0 END) AS maintenance_min,
         sum(CASE WHEN event_type = 'error' THEN 1 ELSE 0 END) AS error_events
  FROM {rs_cat}.{rs_schema}.production_events
  GROUP BY machine_id
  ORDER BY error_events DESC, maintenance_min DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で確認する手順
# MAGIC
# MAGIC 1. **Catalog Explorer** で Redshift foreign catalog → スキーマ → 3 テーブル
# MAGIC 2. テーブルの **Details** で「Connection: <redshift-conn>」= Query Federation であることを確認
# MAGIC 3. `EXPLAIN FORMATTED` の出力に **PushedFilters** / Redshift 側スキャンが現れることを確認
# MAGIC 4. データは Redshift に留まり、Databricks へは結果のみ返る（＝転送コスト最小）
# MAGIC
# MAGIC 次は **`03_cross_source_lineage`** で Glue × Redshift をクロスソース JOIN します。
