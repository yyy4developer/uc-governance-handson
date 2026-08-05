# =============================================================================
# AWS Lake Formation Permissions
# Grants IAM_ALLOWED_PRINCIPALS on databases to opt out of Lake Formation
# =============================================================================

resource "aws_lakeformation_permissions" "iam_database" {
  count = var.enable_glue ? 1 : 0

  principal   = "IAM_ALLOWED_PRINCIPALS"
  permissions = ["ALL"]

  database {
    name = aws_glue_catalog_database.factory_master[0].name
  }
}

# Opt out of Lake Formation for this database entirely
# This ensures all tables (including those created by Glue ETL) are accessible via IAM
resource "aws_lakeformation_data_lake_settings" "opt_out" {
  count = var.enable_glue ? 1 : 0

  create_database_default_permissions {
    principal   = "IAM_ALLOWED_PRINCIPALS"
    permissions = ["ALL"]
  }
  create_table_default_permissions {
    principal   = "IAM_ALLOWED_PRINCIPALS"
    permissions = ["ALL"]
  }
}

# Some sandbox accounts have the pre-existing `default` Glue database opted IN to
# Lake Formation (explicit grants to named roles, no IAM_ALLOWED_PRINCIPALS). The
# Glue ETL Spark job runs with --enable-glue-datacatalog and verifies the
# `default` database on startup, so its role needs DESCRIBE on it. Harmless when
# `default` is already IAM-accessible. Requires the deploying principal to hold
# grant option on `default` (sandbox-admin does).
resource "aws_lakeformation_permissions" "glue_role_default_db" {
  count = var.enable_glue ? 1 : 0

  principal   = aws_iam_role.glue_etl[0].arn
  permissions = ["DESCRIBE"]

  database {
    name = "default"
  }

  depends_on = [aws_lakeformation_data_lake_settings.opt_out]
}

# Same gap on the read path: the Databricks Glue catalog-federation role assumes
# into this account and its Hive metastore client verifies the `default` database
# on init. Without DESCRIBE it fails with EXTERNAL_METASTORE_CLIENT_ERROR.
resource "aws_lakeformation_permissions" "databricks_glue_default_db" {
  count = var.enable_glue ? 1 : 0

  principal   = aws_iam_role.databricks_glue[0].arn
  permissions = ["DESCRIBE"]

  database {
    name = "default"
  }

  depends_on = [aws_lakeformation_data_lake_settings.opt_out]
}
