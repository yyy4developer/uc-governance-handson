# Databricks notebook source
# MAGIC %md
# MAGIC # _config — 共通設定（catalog / schema を1箇所で管理）
# MAGIC
# MAGIC 各ノートブックの冒頭で `%run ./_config` して読み込む共通設定です。
# MAGIC
# MAGIC ## 🧑‍🤝‍🧑 マルチユーザー対応（重要）
# MAGIC
# MAGIC ハンズオンでは**複数の参加者が同じワークスペースで同時に**作業します。
# MAGIC お互いの作業がぶつからないよう、**スキーマは参加者ごとに自動で分けられます**。
# MAGIC
# MAGIC - スキーマ名は**ログインユーザー名から自動生成**されます（例: `taro.yamada@example.com` → `uc_handson_taro_yamada`）
# MAGIC - 手で名前を決める必要はありません。**このファイルを編集せずにそのまま実行**してください
# MAGIC - 自分のスキーマ名は各ノートブック冒頭の出力で確認できます
# MAGIC
# MAGIC ## 環境を変えたいとき（管理者向け）
# MAGIC
# MAGIC - 別のカタログを使う → `DEFAULT_CATALOG` を変更
# MAGIC - 全員で1つのスキーマを共有したい（デモ用）→ `SCHEMA_PER_USER = False` にする

# COMMAND ----------

# ★★★ 管理者が環境に合わせて設定する箇所 ★★★
# 使用するワークスペースの既存カタログ名。
# 別の環境で使う場合はここだけ書き換えてください
# （Catalog Explorer で対象カタログ名を確認、または SELECT current_catalog() の結果を使う）。
DEFAULT_CATALOG = "catalog_azure_nbiwes"

# 参加者ごとにスキーマを分ける（ハンズオンでは True 推奨）
SCHEMA_PER_USER = True
SCHEMA_PREFIX = "uc_handson"

# 参加者グループ名（管理者が Account Console で作成したもの）。
# 03 の RBAC 演習でこのグループに対して GRANT / REVOKE します。
# admin/00_prepare_environment.py の GROUP_NAME と同じ値にしてください。
PARTICIPANT_GROUP = "trail-uc-handson-grp"

# COMMAND ----------

import re


def _user_suffix() -> str:
    """ログインユーザー名からスキーマ名に使える識別子を作る。

    例: taro.yamada@example.com -> taro_yamada
    """
    try:
        email = spark.sql("SELECT current_user()").collect()[0][0]
    except Exception:
        email = "shared"
    local = (email or "shared").split("@")[0]
    # 英数字以外は _ に寄せ、先頭が数字なら u を付ける（識別子として安全な形に）
    ident = re.sub(r"[^0-9a-zA-Z]+", "_", local).strip("_").lower()
    if not ident:
        ident = "shared"
    if ident[0].isdigit():
        ident = f"u{ident}"
    return ident[:40]


DEFAULT_SCHEMA = f"{SCHEMA_PREFIX}_{_user_suffix()}" if SCHEMA_PER_USER else SCHEMA_PREFIX

# COMMAND ----------

# widget があればそれを優先（ジョブ実行時）、無ければ上の既定値（UI 直接実行時）
try:
    dbutils.widgets.text("catalog", DEFAULT_CATALOG, "対象カタログ")
    dbutils.widgets.text("schema", DEFAULT_SCHEMA, "スキーマ名")
    catalog = dbutils.widgets.get("catalog") or DEFAULT_CATALOG
    schema = dbutils.widgets.get("schema") or DEFAULT_SCHEMA
except Exception:
    catalog, schema = DEFAULT_CATALOG, DEFAULT_SCHEMA

FQ = f"{catalog}.{schema}"

spark.sql(f"USE CATALOG {catalog}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {FQ}")
spark.sql(f"USE SCHEMA {schema}")

print("=" * 60)
print(f"  あなたの作業スキーマ: {FQ}")
print(f"  参加者グループ      : {PARTICIPANT_GROUP}")
print("=" * 60)
print("※ 以降のノートブックはこのスキーマに対して実行されます")
