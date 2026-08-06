# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — データ探索（Discovery）
# MAGIC
# MAGIC > 🔑 **必要な権限**: 自分のスキーマの owner（追加付与は不要）
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
# MAGIC `03_access_control` で付けたタグ（`uc_handson_domain` / `uc_handson_layer` / `uc_handson_sensitivity`）で資産を分類・発見します。

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
# MAGIC 1. 画面上部の **検索窓**（`Cmd/Ctrl + P`）に `orders` と入力 → 資産候補が出る
# MAGIC 2. Enter で **Search results** ページへ。**Type**（Table/View など）や **Catalog** で絞り込み
# MAGIC
# MAGIC **B. タグで検索する（⚠️ 上部の検索窓から行います）**
# MAGIC
# MAGIC `03` で定義した**管理タグ**を使って資産を絞り込みます。方法は 2 つあります。
# MAGIC
# MAGIC *方法1: 検索構文で直接指定*
# MAGIC
# MAGIC | 検索したいもの | 入力する構文 |
# MAGIC |---|---|
# MAGIC | タグキーだけ | `tag:uc_handson_domain` |
# MAGIC | キーと値の両方 | `tag:uc_handson_domain:procurement` |
# MAGIC
# MAGIC 1. `Cmd/Ctrl + P` → `tag:uc_handson_domain:procurement` と入力
# MAGIC 2. `part` / `supplier` がヒットすることを確認（`03` で付けたタグが効く）
# MAGIC
# MAGIC *方法2: フィルタから選択（管理タグなら候補に出ます）*
# MAGIC 1. `Cmd/Ctrl + P` → Enter で **Search results** ページを開く
# MAGIC 2. **Type** ドロップダウンで **Tables** を選択
# MAGIC 3. 現れた **Tag** フィルタを開くと `uc_handson_domain` などが**候補として並ぶ**ので選択
# MAGIC
# MAGIC > ⚠️ **Catalog Explorer 左サイドバーのフィルタ欄では、タグ検索はできません**
# MAGIC > （公式ドキュメントに明記: "You cannot use the filter field in Catalog Explorer to search by tag."）。
# MAGIC > タグで探すときは必ず**上部の検索窓**を使ってください。
# MAGIC >
# MAGIC > ⚠️ **完全一致が必要**です（`tag:uc_handson` のような部分一致では見つかりません）。
# MAGIC > タグキーは**大文字小文字を区別**します。
# MAGIC >
# MAGIC > 💡 **通常タグとの違い**: `CREATE GOVERNED TAG` していない通常タグは、
# MAGIC > 検索構文（方法1）では効きますが、**Tag フィルタの候補（方法2）には出ません**
# MAGIC > （現時点のプロダクト制約）。組織的にタグ運用するなら管理タグが有利な理由の一つです。
# MAGIC >
# MAGIC > 💡 検索対象はテーブル / ビュー / モデル / Volume / 関数 / ダッシュボード / ノートブック。
# MAGIC > カタログ・スキーマ・**列**はタグ検索の対象外です。
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
