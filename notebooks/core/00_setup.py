# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — セットアップ
# MAGIC
# MAGIC UC ガバナンス ハンズオン（**Federation なし版**）の土台を用意します。
# MAGIC 対象カタログ配下に **スキーマ** と **Volume** を作成します。
# MAGIC
# MAGIC | 項目 | 値 |
# MAGIC |---|---|
# MAGIC | カタログ | `_config` の `DEFAULT_CATALOG`（既存のものを再利用。`CREATE CATALOG` 権限は前提にしません） |
# MAGIC | スキーマ | `_config` が**ログインユーザー名から自動生成**（例 `uc_handson_taro_yamada`） |
# MAGIC | Volume | `raw`（生成データ・共有ファイル用） |
# MAGIC
# MAGIC 🧑‍🤝‍🧑 **マルチユーザー**: 複数人が同じワークスペースで作業しても、
# MAGIC スキーマが自動で参加者ごとに分かれるため衝突しません。**設定の書き換えは不要**です。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# _config が catalog / schema / FQ を定義し、USE CATALOG / USE SCHEMA まで実行済み
print(f"target = {FQ}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## スキーマ・Volume の作成
# MAGIC
# MAGIC `IF NOT EXISTS` で冪等に作成します（何度実行しても安全）。
# MAGIC
# MAGIC > なし版のソースは Databricks 標準の **`samples.tpch`**（部品調達・受注データ）です。
# MAGIC > `01_ingest_data` で自分のスキーマに取り込み、以降のガバナンス操作を行います。

# COMMAND ----------

spark.sql(f"USE CATALOG {catalog}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema} COMMENT '部品調達・受注 ガバナンス ハンズオン（なし版、samples.tpch 由来）'")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.raw COMMENT 'ランディング領域'")

print(f"✓ Schema : {catalog}.{schema}")
print(f"✓ Volume : /Volumes/{catalog}/{schema}/raw")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 確認

# COMMAND ----------

display(spark.sql(f"SHOW SCHEMAS IN {catalog} LIKE '{schema}'"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で確認する手順（Catalog Explorer）
# MAGIC
# MAGIC 1. 左メニュー **Catalog** を開く
# MAGIC 2. `catalog` → 作成した `schema` を展開
# MAGIC 3. **Volumes** に `raw` があることを確認
# MAGIC 4. スキーマの **Details** タブで COMMENT が表示されることを確認
# MAGIC
# MAGIC 次のノートブック **`01_ingest_data`** で `samples.tpch` を自スキーマに取り込みます。
