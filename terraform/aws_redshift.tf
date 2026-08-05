# =============================================================================
# Amazon Redshift Serverless
# =============================================================================

resource "aws_redshiftserverless_namespace" "demo" {
  count = var.enable_redshift ? 1 : 0

  namespace_name      = "${local.name_prefix}-ns"
  db_name             = local.redshift_db_name
  admin_username      = "admin"
  admin_user_password = var.redshift_admin_password

  tags = {
    Name = "${local.name_prefix}-namespace"
  }
}

resource "aws_redshiftserverless_workgroup" "demo" {
  count = var.enable_redshift ? 1 : 0

  workgroup_name = "${local.name_prefix}-wg"
  namespace_name = aws_redshiftserverless_namespace.demo[0].namespace_name

  base_capacity       = 8
  publicly_accessible = true

  subnet_ids         = aws_subnet.public[*].id
  security_group_ids = [aws_security_group.redshift[0].id]

  tags = {
    Name = "${local.name_prefix}-workgroup"
  }
}
