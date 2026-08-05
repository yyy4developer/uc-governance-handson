# =============================================================================
# UC ガバナンス ハンズオン — Federation あり版の環境構築
# データソースは AWS Glue（Catalog Federation）+ Amazon Redshift（Query Federation）のみ。
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.58"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

resource "random_string" "suffix" {
  length  = 4
  special = false
  upper   = false
}

locals {
  # Random suffix for multi-user uniqueness
  suffix = random_string.suffix.result

  # Resource naming prefix (suffix ensures no collisions between users)
  name_prefix = "${var.project_prefix}-${local.suffix}" # e.g. uc-handson-xbmx

  # Database/schema prefix: use var.db_prefix if set, else derive from project_prefix
  db_prefix = var.db_prefix != "" ? var.db_prefix : replace(var.project_prefix, "-", "_")

  # Source database/schema names
  redshift_db_name = "${local.db_prefix}_factory"

  # Custom schema name within the source database (replaces public)
  source_schema = local.db_prefix
}

# -----------------------------------------------------------------------------
# AWS Provider
# -----------------------------------------------------------------------------
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "uc-governance-handson"
      ManagedBy = "terraform"
    }
  }
}

# -----------------------------------------------------------------------------
# Databricks Provider (workspace-level, OAuth U2M via CLI)
# Run: databricks auth login --host <workspace-url>
# -----------------------------------------------------------------------------
provider "databricks" {
  host = var.databricks_host
}
