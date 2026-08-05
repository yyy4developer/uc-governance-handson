# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — クロスソース分析とリネージ
# MAGIC
# MAGIC **Glue（マスタ）× Redshift（トランザクション）** を `machine_id` でクロスソース JOIN し、
# MAGIC union catalog に統合テーブル `machine_health_summary` を作成します。
# MAGIC 異なるデータソースをまたいだリネージが Unity Catalog で可視化されます。
# MAGIC
# MAGIC > 📖 [データリネージ](https://docs.databricks.com/ja/data-governance/unity-catalog/data-lineage.html)

# COMMAND ----------

dbutils.widgets.text("fed_catalog_glue", "", "Glue foreign catalog 名")
dbutils.widgets.text("fed_catalog_redshift", "", "Redshift foreign catalog 名")
dbutils.widgets.text("fed_union_catalog", "", "Union catalog 名")
glue_cat = dbutils.widgets.get("fed_catalog_glue")
rs_cat = dbutils.widgets.get("fed_catalog_redshift")
union_cat = dbutils.widgets.get("fed_union_catalog")
assert glue_cat and rs_cat and union_cat, "3 つの foreign/union catalog 名が必要です"

# スキーマ名を発見
glue_schemas = [r[0] for r in spark.sql(f"SHOW SCHEMAS IN {glue_cat}").collect()]
master_schema = next((s for s in glue_schemas if s.endswith("factory_master")), glue_schemas[0])
# Redshift: catalog_history / pg_* 等のシステムスキーマを除外し、
# 期待テーブル sensor_readings を実際に含むスキーマを選ぶ。
rs_schemas = [r[0] for r in spark.sql(f"SHOW SCHEMAS IN {rs_cat}").collect()]
_SYS = {"information_schema", "public", "catalog_history"}
_rs_user = [s for s in rs_schemas if s not in _SYS and not s.startswith("pg_")]

def _has_sensor_readings(schema):
    try:
        return "sensor_readings" in {r["tableName"] for r in spark.sql(f"SHOW TABLES IN {rs_cat}.{schema}").collect()}
    except Exception:
        return False

rs_schema = next((s for s in _rs_user if _has_sensor_readings(s)), (_rs_user[0] if _rs_user else "public"))
analysis_schema = "analysis"
print(f"glue     : {glue_cat}.{master_schema}")
print(f"redshift : {rs_cat}.{rs_schema}")
print(f"union    : {union_cat}.{analysis_schema}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 分析スキーマの準備

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {union_cat}.{analysis_schema} COMMENT 'クロスソース分析結果'")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 機械ヘルスサマリーの作成（Glue マスタ × Redshift トランザクション）

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {union_cat}.{analysis_schema}.machine_health_summary
COMMENT 'クロスソース統合: Glue の機械マスタ + Redshift のセンサー/イベント/品質'
AS
WITH sensor_summary AS (
  SELECT machine_id,
         count(CASE WHEN status = 'warning'  THEN 1 END) AS sensor_warnings,
         count(CASE WHEN status = 'critical' THEN 1 END) AS sensor_criticals
  FROM {rs_cat}.{rs_schema}.sensor_readings
  GROUP BY machine_id
),
event_summary AS (
  SELECT machine_id,
         count(CASE WHEN event_type = 'error' THEN 1 END) AS error_count,
         sum(CASE WHEN event_type = 'maintenance' THEN duration_minutes ELSE 0 END) AS maintenance_minutes
  FROM {rs_cat}.{rs_schema}.production_events
  GROUP BY machine_id
),
quality_agg AS (
  SELECT machine_id,
         count(*) AS total_inspections,
         count(CASE WHEN result = 'pass' THEN 1 END) AS passed_inspections,
         count(CASE WHEN result = 'fail' THEN 1 END) AS failed_inspections,
         sum(defect_count) AS total_defects
  FROM {rs_cat}.{rs_schema}.quality_inspections
  GROUP BY machine_id
)
SELECT
  m.machine_id, m.machine_name, m.production_line, m.factory, m.status AS machine_status,
  coalesce(ss.sensor_warnings, 0)     AS sensor_warning_count,
  coalesce(ss.sensor_criticals, 0)    AS sensor_critical_count,
  coalesce(es.error_count, 0)         AS error_event_count,
  coalesce(es.maintenance_minutes, 0) AS total_maintenance_minutes,
  coalesce(qa.total_inspections, 0)   AS total_inspection_count,
  coalesce(qa.passed_inspections, 0)  AS passed_inspection_count,
  coalesce(qa.failed_inspections, 0)  AS failed_inspection_count,
  coalesce(qa.total_defects, 0)       AS total_defect_count,
  round(coalesce(qa.passed_inspections, 0) * 100.0 / nullif(qa.total_inspections, 0), 1) AS quality_pass_rate_pct
FROM {glue_cat}.{master_schema}.machines m
LEFT JOIN sensor_summary ss ON m.machine_id = ss.machine_id
LEFT JOIN event_summary  es ON m.machine_id = es.machine_id
LEFT JOIN quality_agg    qa ON m.machine_id = qa.machine_id
""")
print("✓ machine_health_summary created")

# COMMAND ----------

spark.sql(f"""
  SELECT * FROM {union_cat}.{analysis_schema}.machine_health_summary
  ORDER BY sensor_critical_count DESC, error_event_count DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で確認する手順（クロスソースリネージ）
# MAGIC
# MAGIC 1. **Catalog Explorer** → `union` catalog → `analysis.machine_health_summary` を開く
# MAGIC 2. **Lineage** タブ → **See lineage graph**
# MAGIC 3. 上流に **Glue の machines** と **Redshift の sensor_readings / production_events / quality_inspections**
# MAGIC    が異なるソースとして接続されて見える（＝データソースをまたいだリネージ）
# MAGIC 4. データは移動しておらず、UC がメタデータで統合していることを確認
# MAGIC
# MAGIC 次は **`04_federation_access`** で、この federation カタログにアクセス制御を適用します。
