# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Federation カタログへのアクセス制御
# MAGIC
# MAGIC **ポイント**: なし版（`core/03_access_control`）で学んだ UC のアクセス制御モデルは、
# MAGIC Glue / Redshift の **foreign catalog にもそのまま適用**できます。
# MAGIC 外部データソースであっても、UC が統一的にガバナンスします（＝ガバナンスの一貫性）。
# MAGIC
# MAGIC > 📖 [外部カタログの権限管理](https://docs.databricks.com/ja/query-federation/index.html) ／
# MAGIC > [権限の管理](https://docs.databricks.com/ja/data-governance/unity-catalog/manage-privileges/index.html)

# COMMAND ----------

dbutils.widgets.text("fed_catalog_glue", "", "Glue foreign catalog 名")
dbutils.widgets.text("fed_catalog_redshift", "", "Redshift foreign catalog 名")
glue_cat = dbutils.widgets.get("fed_catalog_glue")
rs_cat = dbutils.widgets.get("fed_catalog_redshift")
assert glue_cat and rs_cat, "fed_catalog_glue / fed_catalog_redshift が必要です"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 現在の権限を確認
# MAGIC
# MAGIC foreign catalog でも `SHOW GRANTS` が同じように使えます。

# COMMAND ----------

display(spark.sql(f"SHOW GRANTS ON CATALOG {rs_cat}"))

# COMMAND ----------

display(spark.sql(f"SHOW GRANTS ON CATALOG {glue_cat}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. GRANT の例（native カタログと同じ構文）
# MAGIC
# MAGIC グループが存在すれば実行、無ければ手順の理解に留めます。

# COMMAND ----------

# MAGIC %md
# MAGIC ```sql
# MAGIC -- 外部カタログ全体の利用権限
# MAGIC GRANT USE CATALOG ON CATALOG <fed_catalog_redshift> TO `line_engineers`;
# MAGIC
# MAGIC -- 特定スキーマ・テーブルの SELECT
# MAGIC GRANT USE SCHEMA ON SCHEMA <fed_catalog_redshift>.<schema> TO `line_engineers`;
# MAGIC GRANT SELECT ON TABLE <fed_catalog_redshift>.<schema>.sensor_readings TO `line_engineers`;
# MAGIC
# MAGIC -- 取消
# MAGIC REVOKE SELECT ON TABLE <fed_catalog_redshift>.<schema>.sensor_readings FROM `line_engineers`;
# MAGIC ```

# COMMAND ----------

def _grant(stmt):
    try:
        spark.sql(stmt); print("✓", stmt)
    except Exception as e:
        print("· skip:", str(e).splitlines()[0][:100])

try:
    have = {r["name"] for r in spark.sql("SHOW GROUPS").collect()}
except Exception:
    have = set()

if "line_engineers" in have:
    _grant(f"GRANT USE CATALOG ON CATALOG {rs_cat} TO `line_engineers`")
    _grant(f"GRANT USE CATALOG ON CATALOG {glue_cat} TO `line_engineers`")
else:
    print("· デモ用グループが無いため GRANT はスキップ。上の SQL 例で手順を確認してください。")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 行フィルタ / 列マスクも foreign catalog に適用可能
# MAGIC
# MAGIC なし版と同じく、foreign テーブルにも行フィルタ・列マスクを適用できます
# MAGIC （Query Federation は関数のサポート状況がソースにより異なるため、まず SHOW GRANTS で確認）。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で設定する手順（foreign catalog への GRANT）
# MAGIC
# MAGIC 1. **Catalog Explorer** で Redshift/Glue の foreign catalog をクリック → **Permissions** タブ
# MAGIC 2. **Grant** ボタン → Principals にグループ（例 `procurement_team`）→ Privileges で `USE CATALOG` / `SELECT` → **Grant**
# MAGIC 3. スキーマ/テーブル単位でも同じ **Permissions → Grant** で付与できる（native と同一 UI）
# MAGIC 4. 取り消しは対象行の **Revoke**
# MAGIC 5. ⭐ 要点: なし版（`core/03`）で操作した画面と**まったく同じ**であること
# MAGIC    — 外部ソース（Glue/Redshift）でもガバナンス体験は変わらない
# MAGIC
# MAGIC 次は **`05_genie_federation`** で、federation データを Genie で探索します。
