# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — データリネージ
# MAGIC
# MAGIC マスタ × トランザクションを JOIN して分析テーブル **`order_analysis_summary`** を作成し、
# MAGIC Unity Catalog が自動で捕捉する **テーブル/列レベルのリネージ** を可視化します。
# MAGIC
# MAGIC > 📖 [データリネージのキャプチャと表示](https://docs.databricks.com/ja/data-governance/unity-catalog/data-lineage.html)
# MAGIC
# MAGIC リネージは **クエリ実行時に自動記録** されます（明示操作は不要）。ここでは JOIN を実行して関係を作ります。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# _config が catalog / schema / FQ を定義し、USE CATALOG / USE SCHEMA まで実行済み
print(f"target = {FQ}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 受注分析サマリーの作成
# MAGIC
# MAGIC `orders` + `lineitem` + `customer` + `part` + `supplier` を JOIN し、
# MAGIC 顧客・市場セグメント別の受注サマリを作成します。

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE order_analysis_summary
# MAGIC COMMENT '受注分析: 顧客・セグメント別の受注金額・数量・サプライヤー数の統合サマリ'
# MAGIC AS
# MAGIC SELECT
# MAGIC   c.c_custkey, c.c_name, c.c_mktsegment,
# MAGIC   n.n_name AS nation,
# MAGIC   count(DISTINCT o.o_orderkey)          AS order_count,
# MAGIC   round(sum(l.l_extendedprice * (1 - l.l_discount)), 2) AS net_revenue,
# MAGIC   sum(l.l_quantity)                     AS total_quantity,
# MAGIC   count(DISTINCT l.l_suppkey)           AS distinct_suppliers,
# MAGIC   count(DISTINCT l.l_partkey)           AS distinct_parts
# MAGIC FROM orders o
# MAGIC JOIN customer c ON o.o_custkey = c.c_custkey
# MAGIC JOIN nation   n ON c.c_nationkey = n.n_nationkey
# MAGIC JOIN lineitem l ON o.o_orderkey = l.l_orderkey
# MAGIC GROUP BY c.c_custkey, c.c_name, c.c_mktsegment, n.n_name;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 純売上が大きい顧客トップ10
# MAGIC SELECT * FROM order_analysis_summary
# MAGIC ORDER BY net_revenue DESC
# MAGIC LIMIT 10;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 派生ビュー（市場セグメント別ロールアップ）
# MAGIC
# MAGIC ビューを作るとリネージがさらに 1 段伸びます。

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE VIEW segment_revenue_view
# MAGIC COMMENT '市場セグメント別の受注サマリ（order_analysis_summary から派生）'
# MAGIC AS
# MAGIC SELECT c_mktsegment,
# MAGIC        count(*)             AS customers,
# MAGIC        sum(order_count)     AS orders,
# MAGIC        round(sum(net_revenue), 2) AS net_revenue,
# MAGIC        sum(total_quantity)  AS quantity
# MAGIC FROM order_analysis_summary
# MAGIC GROUP BY c_mktsegment
# MAGIC ORDER BY net_revenue DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM segment_revenue_view;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で確認する手順（リネージグラフ）
# MAGIC
# MAGIC リネージはクエリ実行時に **自動記録** されるため、UI では「閲覧」が中心です。
# MAGIC
# MAGIC 1. **Catalog** → 対象スキーマ → `order_analysis_summary` テーブルをクリック
# MAGIC 2. **Lineage** タブを開く → 上流/下流のテーブルがリスト表示される
# MAGIC 3. **See lineage graph**（グラフアイコン）をクリック → 依存関係が図で表示される
# MAGIC    - 上流: `orders` / `lineitem` / `customer` / `nation`
# MAGIC    - 下流: `segment_revenue_view`
# MAGIC 4. グラフ上のテーブルノードの **＋** を展開すると、さらに上流/下流を辿れる
# MAGIC 5. **列（カラム）をクリック** → その列がどの上流列に由来するか（列レベルリネージ）がハイライトされる
# MAGIC 6. 右上でノートブック/ジョブ等の **ワークフロー由来**（どの処理が生成したか）も確認できる
# MAGIC
# MAGIC 次は **`05_discovery`** でタグ・検索によるデータ探索を行います。
