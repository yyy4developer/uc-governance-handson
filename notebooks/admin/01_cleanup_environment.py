# Databricks notebook source
# MAGIC %md
# MAGIC # 管理者向け — ハンズオン環境の片付け
# MAGIC
# MAGIC > 🔑 **実行できる人**: **アカウント管理者**（`00_prepare_environment` を実行した人）
# MAGIC
# MAGIC ハンズオンで作成した環境を削除します。`00_prepare_environment` と対になるノートブックです。
# MAGIC
# MAGIC ## 実行の順番（重要）
# MAGIC
# MAGIC ```
# MAGIC   1. 参加者が各自  notebooks/core/99_cleanup     を実行  ← 先にこちら
# MAGIC   2. 管理者が      notebooks/admin/01_cleanup    を実行  ← このノートブック
# MAGIC ```
# MAGIC
# MAGIC 参加者のスキーマが残っていると、タグや権限を先に消すと片付けにくくなります。
# MAGIC **参加者の片付けが終わってから**実行してください
# MAGIC （残っている場合は、このノートブックが検出して一括削除もできます）。
# MAGIC
# MAGIC ## 削除するもの
# MAGIC
# MAGIC | # | 対象 | 補足 |
# MAGIC |---|---|---|
# MAGIC | 1 | 状況確認 | 残っているスキーマ・タグ・共有を先に一覧 |
# MAGIC | 2 | 参加者スキーマ（任意） | 参加者が片付け忘れた分をまとめて削除 |
# MAGIC | 3 | Delta Share / Recipient（任意） | ハンズオンで作られた共有 |
# MAGIC | 4 | **管理タグ 3 種** | アカウント全体のリソース |
# MAGIC | 5 | **参加者グループ** | 削除すると付与した権限もまとめて無効化 |
# MAGIC
# MAGIC ⚠️ **この操作は取り消せません。** 各セクションは個別に `CONFIRM` で制御します。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 設定（`00_prepare_environment` と同じ値にしてください）

# COMMAND ----------

# ★ 対象カタログ名
TARGET_CATALOG = "main"

# ★ 参加者グループ名
GROUP_NAME = "uc_handson_participants"

# ★ 参加者スキーマの接頭辞（_config.py の SCHEMA_PREFIX と同じ）
SCHEMA_PREFIX = "uc_handson"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 状況確認（まずここを実行）
# MAGIC
# MAGIC **何が残っているか**を先に一覧します。この時点では何も削除されません。

# COMMAND ----------

me = spark.sql("SELECT current_user()").collect()[0][0]
print(f"実行ユーザー  : {me}")
print(f"対象カタログ  : {TARGET_CATALOG}")
print(f"参加者グループ: {GROUP_NAME}")
print()

# --- 残っている参加者スキーマ ---
leftover_schemas = []
try:
    rows = spark.sql(f"SHOW SCHEMAS IN {TARGET_CATALOG} LIKE '{SCHEMA_PREFIX}*'").collect()
    leftover_schemas = [r[0] for r in rows]
    print(f"■ 残っている参加者スキーマ: {len(leftover_schemas)} 件")
    for s in leftover_schemas:
        try:
            n = len(spark.sql(f"SHOW TABLES IN {TARGET_CATALOG}.{s}").collect())
            print(f"    - {s}（テーブル {n} 件）")
        except Exception:
            print(f"    - {s}")
    if not leftover_schemas:
        print("    ✓ なし（参加者の片付けが完了しています）")
except Exception as e:
    print("■ 参加者スキーマ: 確認できません —", str(e).splitlines()[0][:130])

# COMMAND ----------

# --- ハンズオンの管理タグ ---
handson_tags = ["uc_handson_sensitivity", "uc_handson_domain", "uc_handson_layer"]

print("■ 管理タグ")
tag_usage = {}
for tag in handson_tags:
    try:
        spark.sql(f"SHOW GRANTS ON GOVERNED TAG {tag}").collect()
        # まだどこかに付与されているか（付与が残っていると削除後に通常タグへ降格する）
        used = spark.sql(f"""
            SELECT count(*) FROM system.information_schema.table_tags WHERE tag_name = '{tag}'
        """).collect()[0][0]
        used += spark.sql(f"""
            SELECT count(*) FROM system.information_schema.column_tags WHERE tag_name = '{tag}'
        """).collect()[0][0]
        tag_usage[tag] = used
        print(f"    - {tag}（付与されている箇所: {used}）")
    except Exception as e:
        msg = str(e).splitlines()[0]
        if "NOT_FOUND" in msg or "does not exist" in msg:
            print(f"    · {tag}: 存在しません（既に削除済み）")
        else:
            print(f"    ⚠️ {tag}: {msg[:120]}")

if any(v > 0 for v in tag_usage.values()):
    print()
    print("  ⚠️ まだ付与が残っているタグがあります。")
    print("     この状態で削除すると、タグは「通常タグ」に降格して残ります")
    print("     （参加者スキーマを削除すれば付与も消えるので、先に §2 を実行するのが確実です）")

# COMMAND ----------

# --- ハンズオンで作られた Delta Share / Recipient ---
print("■ Delta Share / Recipient（ハンズオン由来のもの）")
handson_shares, handson_recipients = [], []
for kind, bucket in [("SHARES", handson_shares), ("RECIPIENTS", handson_recipients)]:
    try:
        rows = spark.sql(f"SHOW {kind}").collect()
        hits = [r[0] for r in rows
                if "order_analysis_share" in str(r[0]) or "partner_recipient" in str(r[0])]
        bucket.extend(hits)
        print(f"    {kind}: {hits if hits else '（なし）'}")
    except Exception as e:
        print(f"    {kind}: 確認できません — {str(e).splitlines()[0][:110]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2.（任意）残っている参加者スキーマを削除
# MAGIC
# MAGIC 参加者が `99_cleanup` を実行し忘れた場合に使います。
# MAGIC **`SCHEMA_PREFIX` で始まるスキーマをすべて削除**するので、上の一覧を必ず確認してください。

# COMMAND ----------

# ★ 残っている参加者スキーマを削除する場合は True
DROP_PARTICIPANT_SCHEMAS = False

# COMMAND ----------

if not DROP_PARTICIPANT_SCHEMAS:
    print("DROP_PARTICIPANT_SCHEMAS = False のためスキップしました。")
    if leftover_schemas:
        print(f"（{len(leftover_schemas)} 件のスキーマが残っています。削除する場合は True に変更）")
elif not leftover_schemas:
    print("削除対象のスキーマはありません。")
else:
    print(f"■ {len(leftover_schemas)} 件のスキーマを削除します\n")
    for s in leftover_schemas:
        try:
            spark.sql(f"DROP SCHEMA IF EXISTS {TARGET_CATALOG}.{s} CASCADE")
            print(f"  ✓ {s}")
        except Exception as e:
            print(f"  ⚠️ {s}: {str(e).splitlines()[0][:150]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3.（任意）Delta Share / Recipient を削除
# MAGIC
# MAGIC 参加者が片付け忘れた共有を削除します。

# COMMAND ----------

# ★ ハンズオン由来の Share / Recipient を削除する場合は True
DROP_SHARES = False

# COMMAND ----------

if not DROP_SHARES:
    print("DROP_SHARES = False のためスキップしました。")
    if handson_shares or handson_recipients:
        print(f"（Share {len(handson_shares)} 件 / Recipient {len(handson_recipients)} 件が残っています）")
else:
    print("■ Delta Share / Recipient の削除\n")
    for name in handson_shares:
        try:
            spark.sql(f"DROP SHARE `{name}`")
            print(f"  ✓ SHARE {name}")
        except Exception as e:
            print(f"  ⚠️ SHARE {name}: {str(e).splitlines()[0][:140]}")
    for name in handson_recipients:
        try:
            spark.sql(f"DROP RECIPIENT `{name}`")
            print(f"  ✓ RECIPIENT {name}")
        except Exception as e:
            print(f"  ⚠️ RECIPIENT {name}: {str(e).splitlines()[0][:140]}")
    if not handson_shares and not handson_recipients:
        print("  削除対象はありません。")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. 管理タグ 3 種を削除
# MAGIC
# MAGIC ⚠️ 管理タグは**アカウント全体**のリソースです。
# MAGIC 他のワークスペースや別の用途で使われていないことを確認してから削除してください。
# MAGIC
# MAGIC 削除すると、そのタグに紐づく `ASSIGN` 権限も一緒に消えます。

# COMMAND ----------

# ★ 管理タグを削除する場合は True
DROP_GOVERNED_TAGS = False

# COMMAND ----------

if not DROP_GOVERNED_TAGS:
    print("DROP_GOVERNED_TAGS = False のためスキップしました。")
    print("削除する場合は上のセルで True に変更してください。")
else:
    print("■ 管理タグの削除\n")
    for tag in handson_tags:
        try:
            spark.sql(f"DROP GOVERNED TAG {tag}")
            print(f"  ✓ {tag}")
        except Exception as e:
            msg = str(e).splitlines()[0]
            if "NOT_FOUND" in msg or "does not exist" in msg:
                print(f"  · スキップ（存在しません）: {tag}")
            else:
                print(f"  ⚠️ {tag}: {msg[:160]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. 参加者グループを削除
# MAGIC
# MAGIC 💡 **グループを削除すると、そのグループに付与した権限はまとめて無効化されます**
# MAGIC （カタログ / メタストア / `system.access` / 管理タグ の各 GRANT を個別に REVOKE する必要はありません）。
# MAGIC
# MAGIC これが「一時グループを作る」方式の利点です。
# MAGIC
# MAGIC ⚠️ ただし**グループの削除自体は notebook から実行できません**
# MAGIC （アカウントレベルの操作のため）。下のセルで状況を確認し、
# MAGIC 表示される手順で Account Console または CLI から削除してください。

# COMMAND ----------

# アカウントレベルのグループ操作は notebook から実行できないため、
# ここでは「まだ残っているか」を確認し、削除手順を案内します。
try:
    rows = spark.sql(f"SHOW GROUPS LIKE '{GROUP_NAME}'").collect()
    if rows:
        print(f"■ グループ '{GROUP_NAME}' はまだ存在します → 下の手順で削除してください")
        print()
        print("  【Account Console での削除】")
        print("    1. Account Console → User management → Groups")
        print(f"    2. {GROUP_NAME} を開く → ⋮ → Delete")
        print()
        print("  【CLI での削除（アカウントプロファイル）】")
        print(f"    databricks account groups list -p <account-profile> \\")
        print(f"      | grep {GROUP_NAME}          # group-id を確認")
        print("    databricks account groups delete <group-id> -p <account-profile>")
        print()
        print("  💡 グループを削除すると、付与した権限（カタログ / メタストア /")
        print("     system.access / 管理タグ ASSIGN）はすべてまとめて無効化されます。")
        print("     個別に REVOKE する必要はありません。")
    else:
        print(f"✓ グループ '{GROUP_NAME}' は見つかりません（削除済み、または未作成）")
except Exception as e:
    print("⚠️ 確認できません:", str(e).splitlines()[0][:150])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. 最終確認

# COMMAND ----------

print("■ 残存確認\n")

# スキーマ
try:
    rows = spark.sql(f"SHOW SCHEMAS IN {TARGET_CATALOG} LIKE '{SCHEMA_PREFIX}*'").collect()
    names = [r[0] for r in rows]
    print(f"  参加者スキーマ: {names if names else '✓ なし'}")
except Exception as e:
    print("  参加者スキーマ: 確認できません —", str(e).splitlines()[0][:110])

# 管理タグ
remaining_tags = []
for tag in handson_tags:
    try:
        spark.sql(f"SHOW GRANTS ON GOVERNED TAG {tag}").collect()
        remaining_tags.append(tag)
    except Exception:
        pass
print(f"  管理タグ      : {remaining_tags if remaining_tags else '✓ なし'}")

# グループ（ワークスペースから見えるか）
try:
    rows = spark.sql(f"SHOW GROUPS LIKE '{GROUP_NAME}'").collect()
    print(f"  参加者グループ: {[r[0] for r in rows] if rows else '✓ なし'}")
except Exception as e:
    print("  参加者グループ: 確認できません —", str(e).splitlines()[0][:110])

# カタログ権限
try:
    rows = spark.sql(f"SHOW GRANTS ON CATALOG {TARGET_CATALOG}").collect()
    grp = [f"{r[0]}:{r[1]}" for r in rows if r[0] == GROUP_NAME]
    print(f"  カタログ権限  : {grp if grp else '✓ グループへの付与なし'}")
except Exception as e:
    print("  カタログ権限  : 確認できません —", str(e).splitlines()[0][:110])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. 手動で確認・削除するもの
# MAGIC
# MAGIC SQL / API で消せないため、画面から操作してください。
# MAGIC
# MAGIC | 対象 | 操作 |
# MAGIC |---|---|
# MAGIC | **Genie スペース**（参加者が `08` で作成） | 各参加者が **Genie** → ⋮ → **Delete**、または管理者が一覧から削除 |
# MAGIC | **Git folder**（参加者が取り込んだリポジトリ） | 各参加者が **Workspace** → ⋮ → **Delete** |
# MAGIC | **ダッシュボード**（`07` で任意作成した場合） | **Dashboards** → ⋮ → **Move to trash** |
# MAGIC | **SQL Warehouse の権限** | Warehouse → **Permissions** から参加者グループを削除（グループ削除で自動的に無効化） |
# MAGIC | **ワークスペース自体** | 検証用に作った環境なら、不要になった時点で削除 |
# MAGIC
# MAGIC ### 参加者アカウントについて
# MAGIC
# MAGIC ハンズオンのために追加したユーザーがいる場合、
# MAGIC **Account Console → User management → Users** から削除できます
# MAGIC （既存社員のアカウントは削除しないよう注意してください）。
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ✅ ここまで完了すれば、ハンズオン環境の片付けは終わりです。
