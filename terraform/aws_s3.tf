# =============================================================================
# S3 Bucket for Glue Table Data
# Stores factory data in Parquet, Delta, and Iceberg formats.
# =============================================================================

resource "aws_s3_bucket" "glue_data" {
  count = var.enable_glue ? 1 : 0

  bucket_prefix = "${local.name_prefix}-glue-data-"
  force_destroy = true

  tags = {
    Name = "${local.name_prefix}-glue-data"
  }
}

resource "aws_s3_bucket_public_access_block" "glue_data" {
  count = var.enable_glue ? 1 : 0

  bucket = aws_s3_bucket.glue_data[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
