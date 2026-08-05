# =============================================================================
# Variables — Glue + Redshift federation only
# =============================================================================

variable "project_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "uc-handson"
}

# --- Federation source toggles (both default true; disable one if not needed) ---
variable "enable_glue" {
  description = "Enable AWS Glue catalog federation"
  type        = bool
  default     = true
}

variable "enable_redshift" {
  description = "Enable Amazon Redshift query federation"
  type        = bool
  default     = true
}

# --- Catalog naming ---
variable "catalog_prefix_query" {
  description = "Prefix for query federation catalogs (e.g. ucf_query_redshift)"
  type        = string
  default     = "ucf_query"
}

variable "catalog_prefix_catalog" {
  description = "Prefix for catalog federation catalogs (e.g. ucf_catalog_glue)"
  type        = string
  default     = "ucf_catalog"
}

variable "analysis_catalog" {
  description = "Catalog name for cross-source analysis results (union catalog)"
  type        = string
  default     = "ucf_union_dbx"
}

variable "db_prefix" {
  description = "Prefix for source database/schema names (default derived from project_prefix)"
  type        = string
  default     = ""
}

# --- Databricks ---
variable "databricks_host" {
  description = "Databricks workspace URL (e.g. https://<workspace>.cloud.databricks.com)"
  type        = string
}

# --- AWS ---
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "redshift_admin_password" {
  description = "Redshift Serverless admin password (min 8 chars: upper + lower + number). Set in terraform.tfvars (gitignored) — never commit. enable_redshift=true の場合は必須。"
  type        = string
  sensitive   = true
  default     = ""

  validation {
    # 空 or 8 文字以上（enable_redshift=true のときは実質必須。空だと Redshift 作成時に失敗する）
    condition     = var.redshift_admin_password == "" || length(var.redshift_admin_password) >= 8
    error_message = "redshift_admin_password must be empty or at least 8 characters."
  }
}
