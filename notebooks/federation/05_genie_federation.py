# Databricks notebook source
# MAGIC %md
# MAGIC > ## 📎 参考実装 — ハンズオン対象外
# MAGIC >
# MAGIC > このノートブックは **Lakehouse Federation** の参考実装です。
# MAGIC > **ハンズオンでは実行しません**（AWS 側のリソース構築が前提で、環境準備に時間とコストがかかるため）。
# MAGIC > ハンズオンで手を動かすのは `notebooks/core/` の 00〜08 です。
# MAGIC >
# MAGIC > 自分の AWS 環境で試す場合は、先に `terraform/` で環境を構築してください。

# COMMAND ----------

# MAGIC %md
# MAGIC # 05 — Genie で federation データを探索
# MAGIC
# MAGIC クロスソースで作った `machine_health_summary`（Glue × Redshift 由来）を Genie スペースに登録し、
# MAGIC 自然言語で分析します。**外部ソース由来のデータでも、native と同じように Genie で扱える**ことを示します。
# MAGIC
# MAGIC > 📖 [AI/BI Genie](https://docs.databricks.com/ja/genie/index.html)

# COMMAND ----------

dbutils.widgets.text("fed_union_catalog", "", "Union catalog 名")
union_cat = dbutils.widgets.get("fed_union_catalog")
assert union_cat, "fed_union_catalog が必要です"
analysis_schema = "analysis"
FQ = f"{union_cat}.{analysis_schema}"
print("target:", FQ)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Genie に含めるテーブル

# COMMAND ----------

display(spark.sql(f"SHOW TABLES IN {FQ}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Genie スペースの instructions（コピペ用）
# MAGIC
# MAGIC ```
# MAGIC あなたは製造業の設備保全・品質データアシスタントです。対象は machine_health_summary。
# MAGIC - factory は工場建屋（A棟/B棟/C棟）、production_line は製造ライン。
# MAGIC - sensor_critical_count は要対応のセンサー異常件数、sensor_warning_count は要観察。
# MAGIC - error_event_count は異常イベント数、total_maintenance_minutes はメンテ総時間。
# MAGIC - quality_pass_rate_pct は品質合格率(%)。failed_inspection_count は不合格数。
# MAGIC - このデータは AWS Glue（機械マスタ）と Amazon Redshift（センサー/イベント/品質）を
# MAGIC   Lakehouse Federation で統合したもの。
# MAGIC 回答は日本語で、根拠となる集計値を添えること。
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## サンプル質問
# MAGIC
# MAGIC - 品質合格率が最も低い機械トップ5は？
# MAGIC - factory（建屋）別の critical センサー件数を教えて
# MAGIC - メンテナンス時間が長い機械はどれ？
# MAGIC - error イベントが多く、かつ品質合格率も低い機械は？

# COMMAND ----------

# MAGIC %md
# MAGIC ## 答え合わせ用の SQL

# COMMAND ----------

spark.sql(f"""
  SELECT machine_id, machine_name, factory, quality_pass_rate_pct, failed_inspection_count
  FROM {FQ}.machine_health_summary
  WHERE total_inspection_count > 0
  ORDER BY quality_pass_rate_pct ASC
  LIMIT 5
""").display()

# COMMAND ----------

spark.sql(f"""
  SELECT factory, sum(sensor_critical_count) AS criticals
  FROM {FQ}.machine_health_summary
  GROUP BY factory ORDER BY criticals DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で作成する手順
# MAGIC
# MAGIC 1. **Genie** → **New** → `machine_health_summary` を追加
# MAGIC 2. Instructions / Sample questions を上記から登録
# MAGIC 3. 質問して、生成 SQL と結果を答え合わせ用 SQL と突き合わせる
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## まとめ（あり版）
# MAGIC
# MAGIC - Glue（Catalog Federation）と Redshift（Query Federation）を **コピーせず** UC 傘下に統合
# MAGIC - クロスソース JOIN とリネージ、アクセス制御、Genie が **なし版と同じ操作**で機能
# MAGIC - **ガバナンスの一貫性** = データがどこにあっても UC で統一的に統治できる、が価値提案の核
