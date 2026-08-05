# =============================================================================
# Outputs — 値は notebook / DAB 変数へ転記して使う
# =============================================================================

# ----- AWS Glue -----
output "s3_bucket_name" {
  description = "S3 bucket for Glue data"
  value       = var.enable_glue ? aws_s3_bucket.glue_data[0].id : null
}

output "glue_database_name" {
  description = "Glue catalog database name"
  value       = var.enable_glue ? aws_glue_catalog_database.factory_master[0].name : null
}

# ----- Redshift -----
output "redshift_endpoint" {
  description = "Redshift Serverless endpoint"
  value       = var.enable_redshift ? aws_redshiftserverless_workgroup.demo[0].endpoint[0].address : null
}

output "redshift_db_name" {
  description = "Redshift database name (foreign catalog の database オプション)"
  value       = var.enable_redshift ? local.redshift_db_name : null
}

# ----- Naming -----
output "suffix" {
  description = "Random suffix used for this deployment"
  value       = local.suffix
}

output "db_prefix" {
  description = "Source database/schema prefix (Redshift の source_schema = この値)"
  value       = local.db_prefix
}

output "source_schema" {
  description = "Redshift 内のスキーマ名（federation notebook の DECLARE 値）"
  value       = local.source_schema
}

# ----- Databricks Catalogs (federation notebook / DAB 変数へ転記) -----
output "databricks_catalogs" {
  description = "Map of deployed Databricks catalogs"
  value = merge(
    var.enable_glue ? { glue = databricks_catalog.glue[0].name } : {},
    var.enable_redshift ? { redshift = databricks_catalog.redshift[0].name } : {},
    { union = databricks_catalog.union.name },
  )
}
