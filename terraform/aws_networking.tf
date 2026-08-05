# =============================================================================
# VPC & Networking for Redshift Serverless
# =============================================================================

locals {
  needs_networking = var.enable_redshift
}

data "aws_availability_zones" "available" {
  count = local.needs_networking ? 1 : 0
  state = "available"
}

resource "aws_vpc" "main" {
  count = local.needs_networking ? 1 : 0

  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${local.name_prefix}-vpc"
  }
}

resource "aws_subnet" "public" {
  count = local.needs_networking ? 3 : 0

  vpc_id            = aws_vpc.main[0].id
  cidr_block        = "10.0.${count.index + 1}.0/24"
  availability_zone = data.aws_availability_zones.available[0].names[count.index]

  map_public_ip_on_launch = true

  tags = {
    Name = "${local.name_prefix}-subnet-${count.index + 1}"
  }
}

resource "aws_internet_gateway" "main" {
  count = local.needs_networking ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  tags = {
    Name = "${local.name_prefix}-igw"
  }
}

resource "aws_route_table" "public" {
  count = local.needs_networking ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main[0].id
  }

  tags = {
    Name = "${local.name_prefix}-rt-public"
  }
}

resource "aws_route_table_association" "public" {
  count = local.needs_networking ? 3 : 0

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_security_group" "redshift" {
  count = var.enable_redshift ? 1 : 0

  name_prefix = "${local.name_prefix}-redshift-"
  vpc_id      = aws_vpc.main[0].id
  description = "Security group for Redshift Serverless"

  ingress {
    description = "Redshift from Databricks - range 1"
    from_port   = 5439
    to_port     = 5439
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/1"]
  }

  ingress {
    description = "Redshift from Databricks - range 2"
    from_port   = 5439
    to_port     = 5439
    protocol    = "tcp"
    cidr_blocks = ["128.0.0.0/1"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-redshift-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}
