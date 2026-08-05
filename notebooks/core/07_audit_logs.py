# Databricks notebook source
# MAGIC %md
# MAGIC # 07 — 監査ログの確認
# MAGIC
# MAGIC Unity Catalog の操作は **system tables**（`system.access.audit`）に記録されます。
# MAGIC 「誰が・いつ・何に」アクセスしたかを SQL で確認します。
# MAGIC
# MAGIC > 📖 公式: [監査ログ system table](https://docs.databricks.com/ja/admin/system-tables/audit-logs.html) ／
# MAGIC > [system table の有効化](https://docs.databricks.com/ja/admin/system-tables/index.html)
# MAGIC
# MAGIC ⚠️ `system` カタログはアカウント管理者が **有効化** している必要があります。
# MAGIC 未有効の場合は下部の UI 手順を参照してください。また監査ログには**数分〜十数分の遅延**があります。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# _config が catalog / schema / FQ を定義済み
print(f"target = {catalog}.{schema}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. system table が使えるか確認

# COMMAND ----------

try:
    spark.sql("SELECT 1 FROM system.access.audit LIMIT 1").collect()
    print("✓ system.access.audit にアクセスできます")
except Exception as e:
    print("✗ system.access.audit にアクセスできません:", str(e).splitlines()[0][:120])
    print("  → アカウント管理者による system schema の有効化が必要（下部 UI 手順参照）")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 直近の自分の操作（本デモの GRANT / SELECT / 共有作成など）

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT event_time, user_identity.email AS user, service_name, action_name,
# MAGIC        request_params
# MAGIC FROM system.access.audit
# MAGIC WHERE event_date >= current_date() - INTERVAL 1 DAY
# MAGIC   AND user_identity.email = current_user()
# MAGIC ORDER BY event_time DESC
# MAGIC LIMIT 50;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. UC 操作にフォーカス（テーブル作成・権限付与・共有）

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT event_time, user_identity.email AS user, action_name,
# MAGIC        request_params.full_name_arg AS object
# MAGIC FROM system.access.audit
# MAGIC WHERE event_date >= current_date() - INTERVAL 1 DAY
# MAGIC   AND service_name = 'unityCatalog'
# MAGIC   AND action_name IN (
# MAGIC     'createTable','generateTemporaryTableCredential','updatePermissions',
# MAGIC     'createShare','updateShare','createRecipient','getTable'
# MAGIC   )
# MAGIC ORDER BY event_time DESC
# MAGIC LIMIT 50;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. テーブルアクセスの集計（誰がどのテーブルを何回参照したか）
# MAGIC
# MAGIC テーブル参照は `getTable` アクションで記録されます（対象は `request_params.full_name_arg`）。
# MAGIC 00〜06 で `customer` / `order_analysis_summary` などを参照しているので、このスキーマの
# MAGIC アクセスが集計されます。
# MAGIC （※ `generateTemporaryTableCredential` は主に外部ストレージ読取時に発生し、キーは
# MAGIC `table_full_name`。UC managed テーブルの通常 SELECT では出ないことがあるため、ここでは
# MAGIC 汎用的な `getTable` を使います。）

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT request_params.full_name_arg AS object,
# MAGIC        user_identity.email          AS accessed_by,
# MAGIC        count(*)                     AS access_count
# MAGIC FROM system.access.audit
# MAGIC WHERE event_date >= current_date() - INTERVAL 7 DAY
# MAGIC   AND action_name = 'getTable'
# MAGIC   AND request_params.full_name_arg LIKE concat(:catalog, '.', :schema, '%')
# MAGIC GROUP BY request_params.full_name_arg, user_identity.email
# MAGIC ORDER BY access_count DESC
# MAGIC LIMIT 50;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. 補足: テーブルリネージ system table
# MAGIC
# MAGIC リネージも system table で参照できます（04 で作った関係が記録される）。

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT source_table_full_name, target_table_full_name, event_time
# MAGIC FROM system.access.table_lineage
# MAGIC WHERE target_table_full_name = concat(:catalog, '.', :schema, '.order_analysis_summary')
# MAGIC ORDER BY event_time DESC
# MAGIC LIMIT 20;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で操作する手順（system table 有効化・監査ダッシュボード）
# MAGIC
# MAGIC **A. system schema の有効化（アカウント管理者、初回のみ）**
# MAGIC 1. **Catalog** → `system` カタログをクリック → `access` スキーマの **Enable** ボタン
# MAGIC    （権限が無い場合は Account Console → **Previews / Settings** から system tables を有効化）
# MAGIC 2. 反映後、`system.access.audit` / `system.access.table_lineage` が SELECT 可能になる
# MAGIC
# MAGIC **B. 監査を確認**
# MAGIC 1. **SQL Editor** で上記クエリを実行（誰が・いつ・何にアクセスしたか）
# MAGIC 2. または Catalog Explorer で `system.access.audit` を開き **Sample data** で中身を確認
# MAGIC
# MAGIC **C. 監査ダッシュボードを UI で作る（実務）**
# MAGIC 1. 上のクエリを SQL Editor で開き **＋ → Add to dashboard**（または AI/BI Dashboard を新規作成）
# MAGIC 2. 「機微テーブルへのアクセス」「権限変更(updatePermissions)」「共有作成(createShare)」を可視化
# MAGIC 3. **Schedule** で定期更新 + アラート設定 → 継続的な監査運用に
# MAGIC
# MAGIC 次は **`08_genie`** で自然言語によるデータ活用を体験します。
