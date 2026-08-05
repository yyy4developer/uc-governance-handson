# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — データ探索（Discovery）
# MAGIC
# MAGIC Unity Catalog 上のデータ資産を **検索・発見** する方法を体験します。
# MAGIC
# MAGIC - `information_schema` によるメタデータ探索（プログラム的）
# MAGIC - タグによる分類・絞り込み
# MAGIC - Catalog Explorer の検索・Certified・Insights（UI）
# MAGIC
# MAGIC > 📖 公式: [情報スキーマ](https://docs.databricks.com/ja/sql/language-manual/sql-ref-information-schema.html) ／
# MAGIC > [データの検索と探索](https://docs.databricks.com/ja/discover/index.html)

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# _config が catalog / schema / FQ を定義し、USE CATALOG / USE SCHEMA まで実行済み
print(f"target = {FQ}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. information_schema でテーブル一覧とコメントを探索

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT table_name, comment
# MAGIC FROM system.information_schema.tables
# MAGIC WHERE table_catalog = :catalog AND table_schema = :schema
# MAGIC ORDER BY table_name;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. カラムを横断検索
# MAGIC
# MAGIC 「部品 ID（`l_partkey` / `p_partkey`）を持つテーブルはどれか」を情報スキーマで探します（結合キーの発見）。

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT table_name, column_name, comment
# MAGIC FROM system.information_schema.columns
# MAGIC WHERE table_catalog = :catalog AND table_schema = :schema
# MAGIC   AND column_name IN ('p_partkey', 'l_partkey')
# MAGIC ORDER BY table_name;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. タグによる絞り込み
# MAGIC
# MAGIC `02_catalog_schema` で付けたタグ（`domain`, `layer`）で資産を分類・発見します。

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT catalog_name, schema_name, table_name, tag_name, tag_value
# MAGIC FROM system.information_schema.table_tags
# MAGIC WHERE catalog_name = :catalog AND schema_name = :schema
# MAGIC ORDER BY table_name, tag_name;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 列レベルタグ（機微データの発見）
# MAGIC SELECT table_name, column_name, tag_name, tag_value
# MAGIC FROM system.information_schema.column_tags
# MAGIC WHERE catalog_name = :catalog AND schema_name = :schema;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で操作する手順（Catalog Explorer 検索・分類）
# MAGIC
# MAGIC **A. 検索で資産を発見**
# MAGIC 1. 画面上部の **検索窓**（またはトップの Search）に `orders` と入力 → 資産候補が出る
# MAGIC 2. 結果を **Type**（Table/View など）や **Catalog** で絞り込み
# MAGIC
# MAGIC **B. タグで絞り込み**
# MAGIC 1. Catalog Explorer 左の **Tags** フィルタ、または検索で `tag:domain=procurement`
# MAGIC 2. `part` / `supplier` がヒットすることを確認（`02` で付けたタグが効く）
# MAGIC
# MAGIC **C. Certified（信頼できる資産）を UI で付与**
# MAGIC 1. `order_analysis_summary` テーブル → 右上 **⋮（kebab）→ Certify**（または Overview の Certified トグル）
# MAGIC 2. 付与すると検索結果・一覧に **Certified バッジ**が表示され、利用者が"正"の資産を見分けられる
# MAGIC 3. 解除は同じメニューから
# MAGIC
# MAGIC **D. Insights / Owner で理解を深める**
# MAGIC 1. テーブル → **Insights** タブ: よく使われるクエリ・頻出結合列・利用者が表示される
# MAGIC 2. **Overview** の **Owner** をクリックすると所有者を変更できる（ガバナンス責任の明確化）
# MAGIC
# MAGIC 次は **`06_delta_sharing`** で組織間データ共有を行います。
