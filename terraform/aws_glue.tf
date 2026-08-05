# =============================================================================
# AWS Glue Catalog Database & Tables
# Factory master data (Parquet, Delta, Iceberg)
# =============================================================================

resource "aws_glue_catalog_database" "factory_master" {
  count = var.enable_glue ? 1 : 0

  name         = local.glue_database_name
  description  = "Lakehouse Federationデモ用の工場マスタデータ"
  location_uri = "s3://${aws_s3_bucket.glue_data[0].id}/factory_master/"
}

# -----------------------------------------------------------------------------
# Table: sensors (Parquet, 20 rows)
# -----------------------------------------------------------------------------

resource "aws_glue_catalog_table" "sensors" {
  count = var.enable_glue ? 1 : 0

  database_name = aws_glue_catalog_database.factory_master[0].name
  name          = "sensors"
  description   = "センサーマスタデータ - 工場内全センサーの種類、単位、設置場所を管理するレジストリ"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "classification" = "parquet"
    "typeOfData"     = "file"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.glue_data[0].id}/factory_master/sensors/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name    = "sensor_id"
      type    = "int"
      comment = "センサーの一意識別子"
    }
    columns {
      name    = "sensor_name"
      type    = "string"
      comment = "センサーのモデル/コード名（例：TMP-A01）"
    }
    columns {
      name    = "sensor_type"
      type    = "string"
      comment = "測定種類：温度、圧力、振動、湿度、流量、回転数"
    }
    columns {
      name    = "unit"
      type    = "string"
      comment = "測定単位（℃、bar、mm/s、%、l/min、rpm）"
    }
    columns {
      name    = "location"
      type    = "string"
      comment = "工場内の物理的な設置場所"
    }
    columns {
      name    = "installed_date"
      type    = "string"
      comment = "センサー設置日（YYYY-MM-DD形式）"
    }
  }

  depends_on = [null_resource.run_glue_job]
}
