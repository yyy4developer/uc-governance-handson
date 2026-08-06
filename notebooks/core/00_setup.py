# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — セットアップ
# MAGIC
# MAGIC > 🔑 **必要な権限**: カタログへの `USE CATALOG` と `CREATE SCHEMA`
# MAGIC > （作成したスキーマの owner になるので、以降の操作は基本これで足ります）
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

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {FQ}")
# スキーマは _config が先に作るため（COMMENT なし）、ここで明示的に説明文を付ける。
# COMMENT ON は既存スキーマにも効くので、何度実行しても同じ結果になる。
spark.sql(f"COMMENT ON SCHEMA {FQ} IS '部品調達・受注 ガバナンス ハンズオン（samples.tpch 由来）'")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {FQ}.raw COMMENT 'ランディング領域（ファイル置き場）'")

print(f"✓ Schema : {FQ}")
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
# MAGIC 💡 **いま作ったものは「入れ物（メタデータ）」です**。
# MAGIC カタログ・スキーマ・Volume はいずれも Unity Catalog が管理する**論理的な構造**で、
# MAGIC この時点ではまだ実データは 1 行もありません。
# MAGIC 次の `01_ingest_data` でデータを入れたあと、**実データが物理的にどこに置かれるのか**を確認します。
# MAGIC
# MAGIC 次のノートブック **`01_ingest_data`** で `samples.tpch` を自スキーマに取り込みます。
