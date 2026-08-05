# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — データ取り込み（samples.tpch → 自スキーマ）
# MAGIC
# MAGIC Databricks 標準サンプル **`samples.tpch`**（部品調達・受注データ）から、自分のスキーマに
# MAGIC native Delta テーブルとして取り込みます。以降のガバナンス操作（COMMENT / タグ / GRANT /
# MAGIC 行フィルタ / リネージ / 共有）は、この自スキーマ上のテーブルで行います。
# MAGIC
# MAGIC | テーブル | 内容 | 主キー | 行数（サブセット） |
# MAGIC |---|---|---|---|
# MAGIC | `region` / `nation` | 地域・国マスタ | r_regionkey / n_nationkey | 5 / 25 |
# MAGIC | `supplier` | サプライヤー | s_suppkey | 1,000 |
# MAGIC | `part` | 部品マスタ | p_partkey | 2,000 |
# MAGIC | `customer` | 顧客 | c_custkey | 1,500 |
# MAGIC | `orders` | 受注 | o_orderkey | 5,000（サブセット） |
# MAGIC | `lineitem` | 受注明細 | (l_orderkey, l_linenumber) | orders に対応する明細 |
# MAGIC
# MAGIC > `orders` / `lineitem` は本来巨大なので、ハンズオン用に受注 5,000 件へ絞り込みます（整合を保って明細も対応分のみ）。
# MAGIC >
# MAGIC > 📖 [samples カタログ](https://docs.databricks.com/ja/discover/databricks-datasets.html)

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# _config が catalog / schema / FQ を定義し、USE CATALOG / USE SCHEMA まで実行済み
print(f"target = {FQ}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 小さいマスタはそのまま複製

# COMMAND ----------

for t in ["region", "nation", "supplier", "part", "customer"]:
    spark.sql(f"CREATE OR REPLACE TABLE {FQ}.{t} AS SELECT * FROM samples.tpch.{t}")
    n = spark.table(f"{FQ}.{t}").count()
    print(f"✓ {FQ}.{t}  ({n} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 受注はサブセット化（5,000 件）し、明細は対応分のみ取り込み
# MAGIC
# MAGIC 巨大テーブルをハンズオン向けに軽量化しつつ、`orders` と `lineitem` の参照整合を保ちます。

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE orders AS
# MAGIC SELECT * FROM samples.tpch.orders
# MAGIC ORDER BY o_orderkey
# MAGIC LIMIT 5000;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- orders に含まれる受注の明細のみを取り込む（整合性を保つ）
# MAGIC CREATE OR REPLACE TABLE lineitem AS
# MAGIC SELECT li.*
# MAGIC FROM samples.tpch.lineitem li
# MAGIC WHERE li.l_orderkey IN (SELECT o_orderkey FROM orders);

# COMMAND ----------

# MAGIC %md
# MAGIC ## 確認

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN {FQ}"))

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 市場セグメント別の顧客数（取り込み確認）
# MAGIC SELECT c_mktsegment, count(*) AS customers
# MAGIC FROM IDENTIFIER(:catalog || '.' || :schema || '.customer')
# MAGIC GROUP BY c_mktsegment ORDER BY customers DESC

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔍 データは物理的にどこにあるのか（UC の要点）
# MAGIC
# MAGIC Unity Catalog は**メタデータを管理する層**であり、実データを自分の中に抱えているわけではありません。
# MAGIC いま作ったテーブルの**実体がどこにあるか**を確認してみましょう。

# COMMAND ----------

# テーブルの物理的な保存場所を確認する
rows = spark.sql(f"DESCRIBE TABLE EXTENDED {FQ}.customer").collect()
info = {r[0]: r[1] for r in rows if r[0]}

print("【Unity Catalog が管理している“見え方”】")
print(f"  カタログ  : {info.get('Catalog')}")
print(f"  スキーマ  : {info.get('Database')}")
print(f"  テーブル  : {info.get('Table')}")
print(f"  種別      : {info.get('Type')}  （MANAGED = UC が実体の置き場所も管理）")
print()
print("【実データが物理的に置かれている場所】")
print(f"  形式      : {info.get('Provider')}")
print(f"  ロケーション: {info.get('Location')}")
print()
print("→ クラウドストレージ（abfss:// や s3://）上のファイルであり、")
print("  UC は『どこに何があり、誰が使えるか』を管理しています（＝仮想的な統合）。")

# COMMAND ----------

# MAGIC %md
# MAGIC ### なぜこれが重要か
# MAGIC
# MAGIC ```
# MAGIC   Unity Catalog（メタデータの層）
# MAGIC     ・テーブルという「見え方」／説明文・タグ／権限・ポリシー／リネージ・監査
# MAGIC             │  「実体はここ」という参照
# MAGIC             ▼
# MAGIC   クラウドストレージ（実データ = Delta 形式のファイル）
# MAGIC ```
# MAGIC
# MAGIC - **この後の操作はすべてメタデータの層で行います**。説明文やタグを付けても（`02`）、
# MAGIC   アクセス制御をかけても（`03`）、**実データのファイルは書き換わりません**。
# MAGIC - Delta Sharing（`06`）で社外に共有するときも、**データをコピーせず**
# MAGIC   「参照する権利」を渡すだけです。
# MAGIC - そして UC がメタデータの層である以上、**自分のストレージ以外**（AWS Glue、Redshift、
# MAGIC   BigQuery など）も同じ枠組みに載せられます → これが **Lakehouse Federation**
# MAGIC   （本日はコンセプトのご紹介のみ）。
# MAGIC
# MAGIC > 📖 [Unity Catalog のデータオブジェクト階層](https://docs.databricks.com/ja/data-governance/unity-catalog/index.html) ／
# MAGIC > [マネージドテーブルと外部テーブル](https://docs.databricks.com/ja/tables/index.html)
# MAGIC
# MAGIC **🖱️ UI でも確認できます**
# MAGIC 1. **Catalog** → 自分のスキーマ → `customer` テーブル
# MAGIC 2. **Details** タブを開く
# MAGIC 3. **Storage location**（保存場所）と **Table type: MANAGED**、**Data source format: DELTA** を確認
# MAGIC
# MAGIC 💡 補足: `MANAGED`（マネージドテーブル）は置き場所も UC が管理する方式です。
# MAGIC 既存のストレージ上のファイルをそのままテーブルとして扱う `EXTERNAL`（外部テーブル）もあり、
# MAGIC どちらも**同じようにガバナンスできます**。

# COMMAND ----------

# MAGIC %md
# MAGIC 次のノートブック **`02_catalog_schema`** で COMMENT・タグ・主キー/外部キー制約を付与し、
# MAGIC ガバナンスの土台（リネージ・Genie の精度向上）を整えます。
