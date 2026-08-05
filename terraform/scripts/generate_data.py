"""
Glue ETL Job: 工場データ生成（複数フォーマット対応）

工場のダミーデータを生成し、S3に3つのフォーマットで書き込む:
  - sensors             → Parquet（テーブル定義はTerraformで管理）
  - machines            → Delta（SparkのsaveAsTableで自動登録、boto3でコメント追加）
  - quality_inspections → Iceberg（Spark Icebergカタログ経由で登録）

必須ジョブパラメータ:
  --S3_BUCKET       : S3バケット名
  --GLUE_DATABASE   : Glueカタログデータベース名
"""

import sys
import json
import boto3
from datetime import datetime, timedelta
import random

from pyspark.context import SparkContext
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, IntegerType, StringType, TimestampType
)
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions

# ---------------------------------------------------------------------------
# ジョブ初期設定
# ---------------------------------------------------------------------------
args = getResolvedOptions(sys.argv, ["JOB_NAME", "S3_BUCKET", "GLUE_DATABASE"])

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

S3_BUCKET = args["S3_BUCKET"]
GLUE_DATABASE = args["GLUE_DATABASE"]
BASE_PATH = f"s3://{S3_BUCKET}/factory_master"

# ★ spark_catalogはデフォルトのまま（Glue Data Catalog = Hiveメタストア）
#   DeltaCatalogに上書きしない！上書きするとGlueへのテーブル登録が壊れる

# Iceberg用Sparkカタログの設定（AWS Glue Data Catalog連携）
spark.conf.set("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.warehouse", f"s3://{S3_BUCKET}/factory_master/")
spark.conf.set("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")

# Glue APIクライアント（メタデータ更新用）
# region は Glue 実行環境の AWS_DEFAULT_REGION を自動参照（未設定時のみ us-west-2）
import os
_REGION = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "us-west-2"
glue_client = boto3.client("glue", region_name=_REGION)
s3_client = boto3.client("s3", region_name=_REGION)

# ---------------------------------------------------------------------------
# 1. センサー (Parquet) - 20行
#    テーブル定義はTerraform（aws_glue_catalog_table.sensors）で管理
#    ここではデータファイルのみをS3に書き込む
# ---------------------------------------------------------------------------
sensors_data = [
    (1,  "TMP-A01", "temperature", "celsius",  "A棟 - ライン1", "2023-01-15"),
    (2,  "TMP-A02", "temperature", "celsius",  "A棟 - ライン1", "2023-01-15"),
    (3,  "TMP-B01", "temperature", "celsius",  "B棟 - ライン2", "2023-03-10"),
    (4,  "TMP-C01", "temperature", "celsius",  "C棟 - ライン3", "2023-06-20"),
    (5,  "PRS-A01", "pressure",    "bar",      "A棟 - ライン1", "2023-01-15"),
    (6,  "PRS-A02", "pressure",    "bar",      "A棟 - ライン1", "2023-02-28"),
    (7,  "PRS-B01", "pressure",    "bar",      "B棟 - ライン2", "2023-03-10"),
    (8,  "PRS-C01", "pressure",    "bar",      "C棟 - ライン3", "2023-06-20"),
    (9,  "VIB-A01", "vibration",   "mm/s",     "A棟 - ライン1", "2023-01-15"),
    (10, "VIB-A02", "vibration",   "mm/s",     "A棟 - ライン1", "2023-02-28"),
    (11, "VIB-B01", "vibration",   "mm/s",     "B棟 - ライン2", "2023-03-10"),
    (12, "VIB-C01", "vibration",   "mm/s",     "C棟 - ライン3", "2023-06-20"),
    (13, "HUM-A01", "humidity",    "percent",  "A棟 - ライン1", "2023-01-15"),
    (14, "HUM-A02", "humidity",    "percent",  "A棟 - ライン1", "2023-04-05"),
    (15, "HUM-B01", "humidity",    "percent",  "B棟 - ライン2", "2023-03-10"),
    (16, "HUM-C01", "humidity",    "percent",  "C棟 - ライン3", "2023-06-20"),
    (17, "FLW-A01", "flow_rate",   "l/min",    "A棟 - ライン1", "2023-05-15"),
    (18, "FLW-B01", "flow_rate",   "l/min",    "B棟 - ライン2", "2023-05-15"),
    (19, "RPM-A01", "rotation",    "rpm",      "A棟 - ライン1", "2023-07-01"),
    (20, "RPM-B01", "rotation",    "rpm",      "B棟 - ライン2", "2023-07-01"),
]

sensors_schema = StructType([
    StructField("sensor_id",      IntegerType(), False),
    StructField("sensor_name",    StringType(),  False),
    StructField("sensor_type",    StringType(),  False),
    StructField("unit",           StringType(),  False),
    StructField("location",       StringType(),  False),
    StructField("installed_date", StringType(),  False),
])

sensors_df = spark.createDataFrame(sensors_data, sensors_schema)
sensors_df.coalesce(1).write.mode("overwrite").parquet(f"{BASE_PATH}/sensors/")

print(f"sensors: {sensors_df.count()} 行をParquetで書き込み完了")

# ---------------------------------------------------------------------------
# 2. 機械 (Delta) - 10行
#    ★ Sparkの saveAsTable でGlueカタログに直接登録する（デフォルトHiveメタストア経由）
#    ★ spark_catalogをDeltaCatalogに上書きしない（上書きするとGlue連携が壊れるため）
#    その後、boto3でテーブル説明・カラムコメントを追加する
# ---------------------------------------------------------------------------
machines_data = [
    (1,  "CNCミル 01",        "ライン1", "A棟", "稼働中"),
    (2,  "CNCミル 02",        "ライン1", "A棟", "稼働中"),
    (3,  "CNC旋盤 01",       "ライン1", "A棟", "稼働中"),
    (4,  "組立ロボット 01",   "ライン2", "B棟", "稼働中"),
    (5,  "組立ロボット 02",   "ライン2", "B棟", "メンテナンス中"),
    (6,  "溶接ステーション 01", "ライン2", "B棟", "稼働中"),
    (7,  "プレス機 01",       "ライン3", "C棟", "稼働中"),
    (8,  "プレス機 02",       "ライン3", "C棟", "停止中"),
    (9,  "検査ユニット 01",   "ライン3", "C棟", "稼働中"),
    (10, "梱包ユニット 01",   "ライン3", "C棟", "稼働中"),
]

# ★ StructFieldのmetadataに"comment"を設定すると、Delta logに書き込まれる
#    DatabricksはDelta logからスキーマを読むため、ここでコメントを設定する必要がある
machines_schema = StructType([
    StructField("machine_id",      IntegerType(), False, metadata={"comment": "機械の一意識別子"}),
    StructField("machine_name",    StringType(),  False, metadata={"comment": "機械の表示名（例：CNCミル01）"}),
    StructField("production_line", StringType(),  False, metadata={"comment": "製造ライン配置（ライン1、ライン2、ライン3）"}),
    StructField("factory",         StringType(),  False, metadata={"comment": "工場建屋の所在地（A棟、B棟、C棟）"}),
    StructField("status",          StringType(),  False, metadata={"comment": "現在の稼働状態：稼働中、メンテナンス中、停止中"}),
])

machines_df = spark.createDataFrame(machines_data, machines_schema)
machines_path = f"{BASE_PATH}/machines"

# Step 1: 既存のGlueテーブルをboto3で削除（前回のboto3/Terraform作成分をクリーンアップ）
try:
    glue_client.delete_table(DatabaseName=GLUE_DATABASE, Name="machines")
    print("machines: 既存のGlueテーブルを削除")
except glue_client.exceptions.EntityNotFoundException:
    print("machines: 既存のGlueテーブルなし（新規作成）")

# Step 2: S3上の古いファイルをクリーンアップ
prefix = "factory_master/machines/"
try:
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        if "Contents" in page:
            objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
            s3_client.delete_objects(Bucket=S3_BUCKET, Delete={"Objects": objects})
    print("machines: S3クリーンアップ完了")
except Exception as e:
    print(f"machines: S3クリーンアップ時のエラー（無視して続行）: {e}")

# Step 3: Delta形式でS3にデータを書き込み
machines_df.coalesce(1).write.format("delta").mode("overwrite").save(machines_path)
print(f"machines: {machines_df.count()} 行をDeltaでS3に書き込み完了")

# Step 4: Spark SQLでGlueカタログにテーブルを登録（カラムコメント付き）
# ★ CREATE TABLE でスキーマとコメントを明示定義する
#    → Delta logにカラムコメントが記録される（DatabricksはDelta logからスキーマを読む）
spark.sql(f"DROP TABLE IF EXISTS `{GLUE_DATABASE}`.`machines`")
spark.sql(f"""
    CREATE TABLE `{GLUE_DATABASE}`.`machines` (
        machine_id INT COMMENT '機械の一意識別子',
        machine_name STRING COMMENT '機械の表示名（例：CNCミル01）',
        production_line STRING COMMENT '製造ライン配置（ライン1、ライン2、ライン3）',
        factory STRING COMMENT '工場建屋の所在地（A棟、B棟、C棟）',
        status STRING COMMENT '現在の稼働状態：稼働中、メンテナンス中、停止中'
    )
    USING delta
    LOCATION '{machines_path}'
""")
print("machines: Glueカタログにテーブル登録完了（カラムコメント付き）")

print(f"machines: {machines_df.count()} 行をDeltaで書き込み＋Glue登録完了")

# Step 5: boto3でテーブル説明とカラムコメント（Glue側）を追加
# Delta logのコメントに加え、Glue StorageDescriptorにもカラム定義を設定する
column_comments_for_glue = {
    "machine_id":      "機械の一意識別子",
    "machine_name":    "機械の表示名（例：CNCミル01）",
    "production_line": "製造ライン配置（ライン1、ライン2、ライン3）",
    "factory":         "工場建屋の所在地（A棟、B棟、C棟）",
    "status":          "現在の稼働状態：稼働中、メンテナンス中、停止中",
}

try:
    # Sparkが登録したテーブル定義を取得
    response = glue_client.get_table(DatabaseName=GLUE_DATABASE, Name="machines")
    table = response["Table"]

    # TableInputに変換（get_tableの応答から不要なフィールドを除外）
    exclude_keys = [
        "DatabaseName", "CreateTime", "UpdateTime", "CreatedBy",
        "IsRegisteredWithLakeFormation", "CatalogId", "VersionId",
        "FederatedTable",
    ]
    table_input = {k: v for k, v in table.items() if k not in exclude_keys}

    # テーブル説明を追加
    table_input["Description"] = "機械マスタデータ - 工場内全機械の製造ライン配置と稼働状態を管理（Deltaフォーマット）"

    # Glue V2カタログの__PLACEHOLDER__をStorageDescriptor.Locationから修正
    if "StorageDescriptor" in table_input:
        sd = table_input["StorageDescriptor"]
        if "__PLACEHOLDER__" in sd.get("Location", ""):
            sd["Location"] = machines_path
            print(f"machines: StorageDescriptor.Location を修正: {machines_path}")

        # pathパラメータも明示的に設定（Databricks HMS Federation用）
        if "Parameters" not in table_input:
            table_input["Parameters"] = {}
        table_input["Parameters"]["path"] = machines_path

    # Sparkのデータソーステーブルは疑似カラム（col: array<string>）のみ登録する
    # → 実際のカラム定義に置き換えて、コメントも同時に設定する
    if "StorageDescriptor" in table_input:
        table_input["StorageDescriptor"]["Columns"] = [
            {"Name": "machine_id",      "Type": "int",    "Comment": column_comments_for_glue["machine_id"]},
            {"Name": "machine_name",    "Type": "string", "Comment": column_comments_for_glue["machine_name"]},
            {"Name": "production_line", "Type": "string", "Comment": column_comments_for_glue["production_line"]},
            {"Name": "factory",         "Type": "string", "Comment": column_comments_for_glue["factory"]},
            {"Name": "status",          "Type": "string", "Comment": column_comments_for_glue["status"]},
        ]

    glue_client.update_table(DatabaseName=GLUE_DATABASE, TableInput=table_input)
    print("machines: テーブル説明・カラムコメント追加完了")

    # 登録されたテーブルのパラメータを確認用に表示
    params = table.get("Parameters", {})
    print(f"machines: spark.sql.sources.provider = {params.get('spark.sql.sources.provider', 'N/A')}")
    print(f"machines: path = {params.get('path', 'N/A')}")
    print(f"machines: Location = {table.get('StorageDescriptor', {}).get('Location', 'N/A')}")
except Exception as e:
    print(f"machines: メタデータ更新時のエラー: {e}")

# ---------------------------------------------------------------------------
# 3. 品質検査 (Iceberg) - 50行
#    Spark Icebergカタログ経由でGlueカタログに登録
# ---------------------------------------------------------------------------
random.seed(42)

inspectors = ["田中", "鈴木", "山本", "渡辺", "小林"]
results = ["pass", "pass", "pass", "pass", "fail", "warning"]  # 合格寄りの重み付け
notes_map = {
    "pass":    ["全パラメータが許容範囲内", "不良なし", "品質OK",
                "目視・寸法検査合格", "表面仕上げ良好"],
    "fail":    ["寸法公差超過", "表面欠陥を検出",
                "材料硬度が仕様未満", "溶接強度不足"],
    "warning": ["軽微な表面傷あり", "振動値がボーダーライン",
                "わずかな変色を確認", "工具摩耗が限界に近い"],
}

base_time = datetime(2025, 1, 15, 6, 0, 0)
qi_data = []
for i in range(1, 51):
    machine_id = random.randint(1, 10)
    inspector = random.choice(inspectors)
    inspection_time = base_time + timedelta(hours=random.randint(0, 720))
    result = random.choice(results)
    defect_count = 0 if result == "pass" else random.randint(1, 5)
    note = random.choice(notes_map[result])
    qi_data.append((i, machine_id, inspector, inspection_time, result, defect_count, note))

qi_schema = StructType([
    StructField("inspection_id",  IntegerType(),   False),
    StructField("machine_id",     IntegerType(),   False),
    StructField("inspector_name", StringType(),    False),
    StructField("inspection_time", TimestampType(), False),
    StructField("result",         StringType(),    False),
    StructField("defect_count",   IntegerType(),   False),
    StructField("notes",          StringType(),    True),
])

qi_df = spark.createDataFrame(qi_data, qi_schema)

# 既存のIcebergテーブルがあれば削除
spark.sql(f"DROP TABLE IF EXISTS glue_catalog.`{GLUE_DATABASE}`.`quality_inspections`")

# Icebergテーブルとして書き込み・登録
iceberg_table = f"glue_catalog.`{GLUE_DATABASE}`.`quality_inspections`"
qi_df.coalesce(1).writeTo(iceberg_table) \
    .using("iceberg") \
    .tableProperty("format-version", "2") \
    .tableProperty("location", f"{BASE_PATH}/quality_inspections") \
    .create()

print(f"quality_inspections: {qi_df.count()} 行をIcebergで書き込み完了")

# Icebergテーブルのメタデータ（テーブル説明・カラムコメント）を設定
spark.sql(f"ALTER TABLE glue_catalog.`{GLUE_DATABASE}`.`quality_inspections` SET TBLPROPERTIES ('comment' = '品質検査結果 - 工場の品質チェック記録（合格/不合格/警告の判定と不良数を含む）')")
spark.sql(f"ALTER TABLE glue_catalog.`{GLUE_DATABASE}`.`quality_inspections` ALTER COLUMN inspection_id COMMENT '検査記録の一意識別子'")
spark.sql(f"ALTER TABLE glue_catalog.`{GLUE_DATABASE}`.`quality_inspections` ALTER COLUMN machine_id COMMENT '検査対象の機械ID（machinesテーブルへの外部キー）'")
spark.sql(f"ALTER TABLE glue_catalog.`{GLUE_DATABASE}`.`quality_inspections` ALTER COLUMN inspector_name COMMENT '品質検査を実施した検査員の名前'")
spark.sql(f"ALTER TABLE glue_catalog.`{GLUE_DATABASE}`.`quality_inspections` ALTER COLUMN inspection_time COMMENT '検査実施のタイムスタンプ'")
spark.sql(f"ALTER TABLE glue_catalog.`{GLUE_DATABASE}`.`quality_inspections` ALTER COLUMN result COMMENT '検査結果：合格（pass）、不合格（fail）、警告（warning）'")
spark.sql(f"ALTER TABLE glue_catalog.`{GLUE_DATABASE}`.`quality_inspections` ALTER COLUMN defect_count COMMENT '発見された不良数（合格の場合は0）'")
spark.sql(f"ALTER TABLE glue_catalog.`{GLUE_DATABASE}`.`quality_inspections` ALTER COLUMN notes COMMENT '検査員による追加メモや所見'")

print("quality_inspections: カラムコメント設定完了")

# ---------------------------------------------------------------------------
# 完了
# ---------------------------------------------------------------------------
job.commit()
print("全データ生成完了")
