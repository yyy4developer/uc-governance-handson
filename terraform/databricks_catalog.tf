# =============================================================================
# Databricks Foreign Catalogs (Glue + Redshift) + Union Catalog
# Mirror external data sources in Unity Catalog
# =============================================================================

# -----------------------------------------------------------------------------
# Catalog Federation: AWS Glue
# -----------------------------------------------------------------------------
resource "databricks_catalog" "glue" {
  count           = var.enable_glue ? 1 : 0
  name            = "${var.catalog_prefix_catalog}_glue"
  connection_name = databricks_connection.glue[0].name

  options = {
    authorized_paths = "s3://${aws_s3_bucket.glue_data[0].id}"
  }

  storage_root = "s3://${aws_s3_bucket.glue_data[0].id}/glue_factory_metadata"

  comment = "外部カタログ: AWS Glue 工場マスタ（sensors, machines, quality_inspections）"

  lifecycle { ignore_changes = [connection_name] }

  depends_on = [databricks_external_location.glue_data]
}

# -----------------------------------------------------------------------------
# Query Federation: Redshift
# -----------------------------------------------------------------------------
resource "databricks_catalog" "redshift" {
  count           = var.enable_redshift ? 1 : 0
  name            = "${var.catalog_prefix_query}_redshift"
  connection_name = databricks_connection.redshift[0].name

  options = {
    database = local.redshift_db_name
  }

  comment = "外部カタログ: Redshift 工場トランザクション（sensor_readings, production_events, quality_inspections）"

  lifecycle { ignore_changes = [connection_name] }
}

# -----------------------------------------------------------------------------
# Union Catalog: cross-source analysis results (machine_health_summary etc.)
# native Databricks catalog (metastore-level storage root を使用)
# -----------------------------------------------------------------------------
resource "databricks_catalog" "union" {
  name    = var.analysis_catalog
  comment = "分析結果カタログ: クロスソース JOIN テーブルを格納（machine_health_summary 等）"

  # この metastore の default storage root は本 principal から書き込み不可（403）のため、
  # union catalog には自前の S3（glue-data バケット配下）を明示的な storage_root として与える。
  # このパスは databricks_external_location.glue_data（書き込み可能）配下にあり、
  # storage IAM role に union_catalog/* への PutObject/DeleteObject 権限を付与済み（aws_iam.tf）。
  storage_root = var.enable_glue ? "s3://${aws_s3_bucket.glue_data[0].id}/union_catalog" : null

  force_destroy = true

  depends_on = [databricks_external_location.glue_data]
}
