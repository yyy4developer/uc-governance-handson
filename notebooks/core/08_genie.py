# Databricks notebook source
# MAGIC %md
# MAGIC # 08 — Genie 体験（自然言語でのデータ活用）
# MAGIC
# MAGIC > 🔑 **必要な権限**: SQL Warehouse への `CAN_USE` と、対象テーブルの `SELECT`
# MAGIC > （自分のスキーマなので満たしています）
# MAGIC
# MAGIC **Genie** は、業務ユーザーが自然言語でデータに質問できる AI/BI 機能です。
# MAGIC UC のメタデータ・コメント・PK/FK 制約（`02` で整備済み）を活用して精度の高い SQL を生成します。
# MAGIC
# MAGIC > 📖 [AI/BI Genie](https://docs.databricks.com/ja/genie/index.html) ／
# MAGIC > [Genie スペースの作成](https://docs.databricks.com/ja/genie/set-up.html)
# MAGIC
# MAGIC Genie スペースの作成は主に **UI 操作** です。本ノートブックでは対象テーブルの確認と、
# MAGIC スペースに与える **instructions / サンプル質問** を用意します。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# _config が catalog / schema / FQ を定義済み
print(f"target = {FQ}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Genie に含めるテーブル（推奨セット）
# MAGIC
# MAGIC マスタ + サマリを中心にすると、業務的な質問に答えやすくなります。

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT table_name, comment
# MAGIC FROM system.information_schema.tables
# MAGIC WHERE table_catalog = :catalog AND table_schema = :schema
# MAGIC   AND table_name IN ('customer','orders','lineitem','part','supplier',
# MAGIC                      'order_analysis_summary')
# MAGIC ORDER BY table_name;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Genie スペースの instructions（コピペ用）
# MAGIC
# MAGIC 以下をスペースの **Instructions** に貼り付けると、用語や粒度が安定します。
# MAGIC
# MAGIC ```
# MAGIC あなたは部品調達・受注データのアシスタントです。
# MAGIC - orders は受注ヘッダ、lineitem は受注明細（部品・サプライヤー・数量・価格）。
# MAGIC - 純売上 = sum(l_extendedprice * (1 - l_discount))。
# MAGIC - c_mktsegment は顧客の市場セグメント（AUTOMOBILE / BUILDING / MACHINERY 等）。
# MAGIC - part は部品マスタ、supplier はサプライヤー。l_partkey / l_suppkey で結合。
# MAGIC - 「受注サマリ」や「顧客別の売上」を聞かれたら order_analysis_summary を優先的に使う。
# MAGIC 回答は日本語で、根拠となる集計値を添えること。
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. サンプル質問（デモ用）
# MAGIC
# MAGIC - 市場セグメント別の純売上を多い順に教えて
# MAGIC - 純売上が最も大きい顧客トップ5は？
# MAGIC - 最も多く発注されている部品は？
# MAGIC - サプライヤー数が最も多い顧客は？
# MAGIC - AUTOMOBILE セグメントの受注件数は？

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. サンプル質問を SQL で先に検証（Genie の答え合わせ用）

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 市場セグメント別の純売上（多い順）
# MAGIC SELECT c_mktsegment, round(sum(net_revenue), 2) AS net_revenue
# MAGIC FROM IDENTIFIER(:catalog || '.' || :schema || '.order_analysis_summary')
# MAGIC GROUP BY c_mktsegment ORDER BY net_revenue DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- 純売上が大きい顧客 トップ5
# MAGIC SELECT c_name, c_mktsegment, net_revenue
# MAGIC FROM IDENTIFIER(:catalog || '.' || :schema || '.order_analysis_summary')
# MAGIC ORDER BY net_revenue DESC LIMIT 5;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🖱️ UI で作成する手順（Genie スペース）
# MAGIC
# MAGIC 1. 左メニュー **Genie** → **New**（または **＋ New → Genie space**）
# MAGIC 2. **Settings → SQL warehouse** でこの環境の Serverless warehouse を選択
# MAGIC 3. **Data** タブ → **Add tables** → 対象スキーマの `order_analysis_summary` とマスタ（customer/orders/part/supplier）を追加
# MAGIC 4. **Instructions** タブ → 上の「2」のテキストを貼り付け → **Save**
# MAGIC 5. **Sample questions** → 上の「3」を 1 問ずつ登録
# MAGIC 6. （任意）**Trusted assets / Example SQL**: 上の「4」の検証済み SQL を「certified query」として登録
# MAGIC    （関数/クエリ名を付けて保存 → Genie が優先的に使い回答が安定）
# MAGIC 7. 右のチャットで質問を入力 → 生成された SQL（**Show generated code**）と結果を、`4` の検証結果と突き合わせる
# MAGIC
# MAGIC これで **なし版のガバナンス 7 項目**（カタログ作成 → アクセス制御 → リネージ → 探索 →
# MAGIC Delta Sharing → 監査ログ → Genie）は完了です。
# MAGIC 続けて **`notebooks/federation/`** で、Glue / Redshift を UC 傘下に取り込む **あり版** に進みます。
