# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — 環境構築の理解（Federation あり版の前提）
# MAGIC
# MAGIC あり版では、**AWS Glue**（Catalog Federation）と **Amazon Redshift**（Query Federation）に
# MAGIC 散在する工場データを、コピーせず Unity Catalog 傘下に取り込みます。
# MAGIC
# MAGIC このノートブックは、そのために必要な **リソースと作成手順** を公式ドキュメント付きで説明し、
# MAGIC 最後に **前提が整っているか（foreign catalog が見えるか）** を確認します。
# MAGIC
# MAGIC > 本デモでは、以下のリソースは `terraform/` で自動構築します。ここでは「各リソースが何をしているか」を理解します。
# MAGIC > Terraform を使わず手動で作る場合の UI 手順も併記します。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 必要なリソースと役割
# MAGIC
# MAGIC | # | リソース | 役割 | 公式ドキュメント |
# MAGIC |---|---|---|---|
# MAGIC | 1 | **IAM ロール**（Glue API 読取 / S3 読取） | Databricks が Glue メタデータと S3 データにアクセスする権限 | [Glue federation](https://docs.databricks.com/ja/query-federation/hive-metastore.html) |
# MAGIC | 2 | **Service Credential**（Glue） | Glue API アクセス用の UC 資格情報 | [service credentials](https://docs.databricks.com/ja/connect/unity-catalog/service-credentials.html) |
# MAGIC | 3 | **Storage Credential**（S3） | S3 データ読取用の UC 資格情報 | [storage credentials](https://docs.databricks.com/ja/connect/unity-catalog/cloud-storage/storage-credentials.html) |
# MAGIC | 4 | **External Location**（S3） | S3 パスへのアクセスをガバナンス | [external locations](https://docs.databricks.com/ja/connect/unity-catalog/cloud-storage/external-locations.html) |
# MAGIC | 5 | **Connection**（GLUE / REDSHIFT） | 外部データソースへの接続定義 | [connections (CREATE CONNECTION)](https://docs.databricks.com/ja/query-federation/index.html) |
# MAGIC | 6 | **Foreign Catalog** | 接続を UC のカタログとしてミラーリング | [foreign catalog](https://docs.databricks.com/ja/query-federation/index.html) |
# MAGIC
# MAGIC - **Glue = Catalog Federation**: メタデータ API 経由でテーブル定義を取得 → S3 上のデータを Databricks が **直接読取**（Spark）
# MAGIC - **Redshift = Query Federation**: JDBC 経由でクエリを **Redshift 側にプッシュダウン** → 結果のみ返却
# MAGIC
# MAGIC > 📖 まず読む: [Lakehouse Federation とは](https://docs.databricks.com/ja/query-federation/index.html) ／
# MAGIC > [Redshift への接続](https://docs.databricks.com/ja/query-federation/redshift.html) ／
# MAGIC > [AWS Glue への接続](https://docs.databricks.com/ja/query-federation/hive-metastore.html)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Terraform での構築（推奨）
# MAGIC
# MAGIC ```bash
# MAGIC cd terraform
# MAGIC cp terraform.tfvars.example terraform.tfvars   # databricks_host, redshift_admin_password を設定
# MAGIC terraform init
# MAGIC terraform apply     # 上表 1〜6 のリソースをすべて作成 + Glue/Redshift にサンプルデータ投入
# MAGIC
# MAGIC # 出力された catalog 名を控える
# MAGIC terraform output databricks_catalogs
# MAGIC terraform output source_schema
# MAGIC ```
# MAGIC
# MAGIC `terraform output databricks_catalogs` の値（`glue` / `redshift` / `union`）を、
# MAGIC このノートブック群の widget（`fed_catalog_glue` / `fed_catalog_redshift` / `fed_union_catalog`）に設定します。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 手動で作る場合の UI 手順（Terraform を使わないとき）
# MAGIC
# MAGIC 1. **Catalog Explorer** → 右上 **+ Add** → **Add a connection**
# MAGIC 2. Connection type に **Redshift** を選び、host / port(5439) / user / password を入力 → 作成
# MAGIC 3. その接続から **Create catalog**（foreign catalog）→ database に Redshift の DB 名を指定
# MAGIC 4. Glue は **Add a connection** → **Glue**、IAM ロール（service credential）を指定
# MAGIC 5. S3 は **External Data** → **Credentials / External Locations** で storage credential + external location を作成
# MAGIC 6. 作成済みなら以下のセルで確認できる

# COMMAND ----------

dbutils.widgets.text("fed_catalog_glue", "", "Glue foreign catalog 名")
dbutils.widgets.text("fed_catalog_redshift", "", "Redshift foreign catalog 名")
dbutils.widgets.text("fed_union_catalog", "", "Union catalog 名")

glue_cat = dbutils.widgets.get("fed_catalog_glue")
rs_cat = dbutils.widgets.get("fed_catalog_redshift")
union_cat = dbutils.widgets.get("fed_union_catalog")
print("glue     :", glue_cat or "(未設定)")
print("redshift :", rs_cat or "(未設定)")
print("union    :", union_cat or "(未設定)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 前提チェック: foreign catalog が UC に見えるか

# COMMAND ----------

rows = spark.sql("SHOW CATALOGS").collect()
catalogs = {r[0] for r in rows}
for label, name in [("Glue", glue_cat), ("Redshift", rs_cat), ("Union", union_cat)]:
    if not name:
        print(f"· {label}: widget 未設定（terraform output を設定してください）")
    elif name in catalogs:
        print(f"✓ {label}: {name} が UC に存在")
    else:
        print(f"✗ {label}: {name} が見つからない（terraform apply 済みか確認）")

# COMMAND ----------

# MAGIC %md
# MAGIC 前提が整っていれば、**`01_glue_catalog_fed`** に進みます。
