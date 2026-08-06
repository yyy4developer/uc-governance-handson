# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Delta Sharing（組織間のデータ共有）
# MAGIC
# MAGIC > 🔑 **必要な権限**: メタストアへの **`CREATE SHARE`** と **`CREATE RECIPIENT`**
# MAGIC > （既定では付いていません。管理者が参加者グループに `GRANT ... ON METASTORE` で付与）
# MAGIC
# MAGIC **Delta Sharing** で、データをコピーせずに組織内外へ安全に共有します。
# MAGIC
# MAGIC - **D2D**（Databricks-to-Databricks）: 相手も Databricks の場合。metastore ID で接続
# MAGIC - **D2O**（Open Sharing）: 相手が Databricks 以外（BI ツール・pandas 等）。activation link + token
# MAGIC
# MAGIC > 📖 公式: [Delta Sharing とは](https://docs.databricks.com/ja/delta-sharing/index.html) ／
# MAGIC > [共有の作成と管理](https://docs.databricks.com/ja/delta-sharing/create-share.html)
# MAGIC
# MAGIC ⚠️ **セキュリティ**: recipient の **activation token を notebook にハードコードしない**こと。
# MAGIC token は UI / activation link 経由で安全に受け渡します。本ノートブックでは SHARE / RECIPIENT の
# MAGIC 作成手順までを扱い、token は UI で確認します。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# _config が catalog / schema / FQ を定義し、USE CATALOG / USE SCHEMA まで実行済み
print(f"target = {FQ}")

# 共有名はユーザー別に一意化（衝突回避）
user = spark.sql("SELECT current_user()").collect()[0][0]
user_token = user.split("@")[0].replace(".", "_").replace("-", "_")
share_name = f"order_analysis_share_{user_token}"
recipient_name = f"partner_recipient_{user_token}"
print("share:", share_name, "| recipient:", recipient_name)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. SHARE の作成とテーブル追加
# MAGIC
# MAGIC 分析結果 `order_analysis_summary`（04 で作成）を共有対象にします。

# COMMAND ----------

spark.sql(f"CREATE SHARE IF NOT EXISTS {share_name} COMMENT '受注分析サマリの共有（デモ）'")
spark.sql(f"ALTER SHARE {share_name} ADD TABLE {FQ}.order_analysis_summary")
display(spark.sql(f"SHOW ALL IN SHARE {share_name}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2-A. D2D（Databricks-to-Databricks）の RECIPIENT
# MAGIC
# MAGIC 相手も Databricks の場合、相手の **metastore 共有 ID** を指定して recipient を作ります。
# MAGIC （相手先の metastore ID は先方に `SELECT current_metastore()` 等で確認してもらう）

# COMMAND ----------

# MAGIC %md
# MAGIC ```sql
# MAGIC -- 例（相手の metastore ID を指定）
# MAGIC CREATE RECIPIENT IF NOT EXISTS <recipient_d2d>
# MAGIC USING ID 'aws:us-west-2:<metastore-uuid>'
# MAGIC COMMENT 'パートナー社（Databricks 利用）';
# MAGIC
# MAGIC GRANT SELECT ON SHARE <share_name> TO RECIPIENT <recipient_d2d>;
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2-B. D2O（Open Sharing）の RECIPIENT
# MAGIC
# MAGIC 相手が Databricks 以外の場合、token ベースの recipient を作成します。
# MAGIC 作成後、**activation link** が発行され、そこから相手が認証情報ファイル（token 含む）を取得します。

# COMMAND ----------

# token ベース recipient を作成（USING ID を付けない = open sharing）
spark.sql(f"CREATE RECIPIENT IF NOT EXISTS {recipient_name} COMMENT 'パートナー社（Open Sharing）'")
spark.sql(f"GRANT SELECT ON SHARE {share_name} TO RECIPIENT {recipient_name}")
# activation link を確認（token 本体は表示しない運用が安全）
display(spark.sql(f"DESCRIBE RECIPIENT {recipient_name}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 後片付け（任意）

# COMMAND ----------

# MAGIC %md
# MAGIC ```sql
# MAGIC -- DROP RECIPIENT <recipient>;
# MAGIC -- DROP SHARE <share_name>;
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で設定する手順（Delta Sharing）
# MAGIC
# MAGIC 上のセルは SQL で作成しましたが、**Share / Recipient は UI から完結**できます。
# MAGIC
# MAGIC **A. Share を UI で作成しテーブルを追加**
# MAGIC 1. **Catalog** → 左メニュー **Delta Sharing** → **Shared by me** タブ → **Share data**
# MAGIC 2. Share 名を入力（例 `order_analysis_share_<自分>`）→ **Save and continue**
# MAGIC 3. **Add data assets** → `order_analysis_summary` を選択 → **Save**
# MAGIC
# MAGIC **B. Recipient を UI で作成し付与**
# MAGIC 1. **Delta Sharing** → **Shared by me** → **New recipient**
# MAGIC 2. **D2O（Open Sharing）**: Sharing identifier を空にして token ベースで作成
# MAGIC    → 作成後に表示される **activation link** をコピー（🔑 token は link からのみ取得、画面外に出さない）
# MAGIC 3. **D2D**: 相手の共有 ID（`aws:region:metastore-uuid`）を入力して作成
# MAGIC 4. Share 画面 → **Recipients** → **Add recipient** で作成した recipient を紐付け（= `GRANT SELECT ON SHARE`）
# MAGIC
# MAGIC **C. 受信側（D2O）**
# MAGIC - 相手は activation link から `config.share` を DL → pandas / BI ツールから読み取り
# MAGIC
# MAGIC ⚠️ recipient token は UI/activation link 経由でのみ扱い、notebook やチャットに貼らないこと。
# MAGIC
# MAGIC 次は **`07_audit_logs`** で操作の監査ログを確認します。
