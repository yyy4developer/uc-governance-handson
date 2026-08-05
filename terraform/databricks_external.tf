# =============================================================================
# Databricks External Location
# Governs access to S3 path where Glue table data is stored.
# =============================================================================

resource "databricks_external_location" "glue_data" {
  count           = var.enable_glue ? 1 : 0
  name            = "${local.name_prefix}-glue-data"
  url             = "s3://${aws_s3_bucket.glue_data[0].id}"
  credential_name = databricks_storage_credential.glue_storage[0].name
  skip_validation = true

  comment = "External location for Glue factory data"

  depends_on = [aws_iam_role.databricks_storage, aws_iam_role_policy.s3_read_access]
}
