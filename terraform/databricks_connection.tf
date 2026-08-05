# =============================================================================
# Databricks Connections for Lakehouse Federation (Glue + Redshift)
# =============================================================================

# AWS Glue (Catalog Federation)
resource "databricks_connection" "glue" {
  count           = var.enable_glue ? 1 : 0
  name            = "${local.name_prefix}-glue-conn"
  connection_type = "GLUE"

  options = {
    aws_region     = var.aws_region
    aws_account_id = data.aws_caller_identity.current.account_id
    credential     = databricks_credential.glue_service[0].name
  }

  comment = "Connection to AWS Glue catalog"
}

# Amazon Redshift (Query Federation)
resource "databricks_connection" "redshift" {
  count           = var.enable_redshift ? 1 : 0
  name            = "${local.name_prefix}-redshift-conn"
  connection_type = "REDSHIFT"

  options = {
    host     = aws_redshiftserverless_workgroup.demo[0].endpoint[0].address
    port     = "5439"
    user     = "admin"
    password = var.redshift_admin_password
  }

  comment = "Connection to Redshift Serverless"
}
