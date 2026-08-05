# =============================================================================
# Databricks Credentials for Lakehouse Federation
#
# Credentials are created BEFORE IAM roles (constructed ARN pattern).
# =============================================================================

# Service Credential: Glue API access
resource "databricks_credential" "glue_service" {
  count   = var.enable_glue ? 1 : 0
  name    = "${local.name_prefix}-glue-service-cred"
  purpose = "SERVICE"

  aws_iam_role {
    role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.glue_role_name}"
  }

  comment = "Service credential for AWS Glue API access"
}

# Storage Credential: S3 data access
resource "databricks_storage_credential" "glue_storage" {
  count = var.enable_glue ? 1 : 0
  name  = "${local.name_prefix}-glue-storage-cred"

  aws_iam_role {
    role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.storage_role_name}"
  }

  comment = "Storage credential for Glue S3 data access"
}
