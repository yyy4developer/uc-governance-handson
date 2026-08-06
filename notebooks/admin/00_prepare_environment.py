# Databricks notebook source
# MAGIC %md
# MAGIC # 管理者向け — ハンズオン環境の事前準備（これ1本で完了）
# MAGIC
# MAGIC > 🔑 **実行できる人**: **アカウント管理者**（`system.access` の付与に必要）
# MAGIC > ＋ カタログの owner または `MANAGE` 権限を持つ人
# MAGIC
# MAGIC ハンズオン当日までに必要な準備を、**このノートブック 1 本**で実施します。
# MAGIC
# MAGIC ## やること
# MAGIC
# MAGIC | # | 内容 | なぜ必要か |
# MAGIC |---|---|---|
# MAGIC | 1 | 前提チェック | 権限・カタログ・`samples` の存在を先に確認 |
# MAGIC | 2 | **参加者への権限付与** | カタログ利用 / Delta Sharing / 監査ログ |
# MAGIC | 3 | **管理タグ 3 種の作成** | ABAC の起点。全員で共有する定義 |
# MAGIC | 4 | **タグの ASSIGN 権限付与** | 参加者がタグを付けられるようにする |
# MAGIC | 5 | 最終確認 | 付与結果を一覧して確認 |
# MAGIC
# MAGIC ## 使い方
# MAGIC
# MAGIC 1. 下の **設定** セルで `TARGET_CATALOG` を書き換える
# MAGIC 2. **▶ Run all** で実行
# MAGIC 3. 出力の ✓ / ⚠️ を確認（⚠️ が出たら対処方法が表示されます）
# MAGIC
# MAGIC > ⚠️ **前日までに実行してください**。権限やタグの反映に**数分**かかることがあります。
# MAGIC >
# MAGIC > 💡 参加者が作業する `notebooks/core/` は触りません。このノートブックは環境準備専用です。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 設定（ここだけ書き換えてください）

# COMMAND ----------

# ★★★ 対象カタログ名（参加者がスキーマを作るカタログ） ★★★
TARGET_CATALOG = "main"

# ★★★ 権限を付与する対象 ★★★
# 全ユーザーに配る場合は "account users"（Unity Catalog の全体グループ）。
# 参加者だけに絞る場合は、事前に作成したグループ名（例 "uc_handson_participants"）に変更。
# ※ ワークスペースローカルの "users" は UC の principal として使えません
PARTICIPANT_PRINCIPAL = "account users"

# 監査ログ（07）を参加者に実行させるか
#   True  → system.access に SELECT を付与（⚠️ アカウント全体の監査ログが見えます）
#   False → 付与しない（07 は講師が画面共有で説明）
GRANT_AUDIT_ACCESS = True

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 前提チェック
# MAGIC
# MAGIC 実行前に、**満たしていない前提がないか**を確認します。ここで問題が見つかれば、
# MAGIC 後続の付与が失敗する前に対処できます。

# COMMAND ----------

ok, warn = [], []


def check(label: str, fn):
    """前提を1つ確認する。例外は警告として集約する"""
    try:
        result = fn()
        if result is True:
            ok.append(label)
            print(f"  ✓ {label}")
        else:
            warn.append(f"{label}: {result}")
            print(f"  ⚠️ {label} — {result}")
    except Exception as e:
        msg = str(e).splitlines()[0][:160]
        warn.append(f"{label}: {msg}")
        print(f"  ⚠️ {label} — {msg}")


me = spark.sql("SELECT current_user()").collect()[0][0]
print(f"実行ユーザー: {me}")
print(f"対象カタログ: {TARGET_CATALOG}")
print(f"付与先        : {PARTICIPANT_PRINCIPAL}")
print()

print("■ 前提チェック")


def _catalog_exists():
    rows = spark.sql(f"SHOW CATALOGS LIKE '{TARGET_CATALOG}'").collect()
    return True if rows else f"カタログ '{TARGET_CATALOG}' が見つかりません（名前を確認してください）"


def _can_manage_catalog():
    # owner か MANAGE があるかは GRANT を試すのが確実だが、ここでは owner 確認に留める
    spark.sql(f"SHOW GRANTS ON CATALOG {TARGET_CATALOG}").collect()
    return True


def _samples_ok():
    n = spark.sql("SELECT count(*) FROM samples.tpch.customer").collect()[0][0]
    return True if n > 0 else "samples.tpch.customer が空です"


def _system_access_ok():
    spark.sql("SELECT 1 FROM system.access.audit LIMIT 1").collect()
    return True


check(f"カタログ {TARGET_CATALOG} が存在する", _catalog_exists)
check("カタログの権限を参照できる（owner / MANAGE）", _can_manage_catalog)
check("samples.tpch が読める", _samples_ok)
if GRANT_AUDIT_ACCESS:
    check("system.access.audit が有効（未有効ならアカウント設定で有効化）", _system_access_ok)

print()
if warn:
    print(f"⚠️ {len(warn)} 件の確認事項があります。下の付与が失敗する場合はここを見直してください。")
else:
    print("✓ 前提はすべて満たしています。次のセルへ進んでください。")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 参加者への権限付与
# MAGIC
# MAGIC | 付与内容 | 使う notebook |
# MAGIC |---|---|
# MAGIC | `USE CATALOG` + `CREATE SCHEMA`（カタログ） | `00`〜`05`（自分のスキーマを作る） |
# MAGIC | `CREATE SHARE` + `CREATE RECIPIENT`（メタストア） | `06`（Delta Sharing） |
# MAGIC | `USE SCHEMA` + `SELECT`（`system.access`） | `07`（監査ログ）※ 任意 |

# COMMAND ----------

results = []


def grant(stmt: str, label: str, hint: str = ""):
    """付与を実行し、失敗時は原因の手がかりを表示する"""
    try:
        spark.sql(stmt)
        print(f"  ✓ {label}")
        results.append(("ok", label))
    except Exception as e:
        msg = str(e).splitlines()[0]
        print(f"  ⚠️ {label}")
        print(f"      → {msg[:180]}")
        if hint:
            print(f"      💡 {hint}")
        results.append(("ng", label))


P = f"`{PARTICIPANT_PRINCIPAL}`"

print("■ カタログ（自分のスキーマを作れるようにする）")
grant(f"GRANT USE CATALOG, CREATE SCHEMA ON CATALOG {TARGET_CATALOG} TO {P}",
      f"USE CATALOG + CREATE SCHEMA on {TARGET_CATALOG}",
      "カタログの owner または MANAGE 権限が必要です")

print("\n■ メタストア（Delta Sharing / 06 で使用）")
grant(f"GRANT CREATE SHARE ON METASTORE TO {P}",
      "CREATE SHARE on METASTORE",
      "メタストア管理者またはアカウント管理者で実行してください")
grant(f"GRANT CREATE RECIPIENT ON METASTORE TO {P}",
      "CREATE RECIPIENT on METASTORE",
      "メタストア管理者またはアカウント管理者で実行してください")

if GRANT_AUDIT_ACCESS:
    print("\n■ 監査ログ（system.access / 07 で使用）")
    print("  ⚠️ 注意: 参加者はアカウント全体の監査ログを読めるようになります")
    grant(f"GRANT USE SCHEMA ON SCHEMA system.access TO {P}",
          "USE SCHEMA on system.access",
          "アカウント管理者で実行してください。system スキーマの有効化も必要です")
    grant(f"GRANT SELECT ON SCHEMA system.access TO {P}",
          "SELECT on system.access",
          "アカウント管理者で実行してください")
else:
    print("\n■ 監査ログ: GRANT_AUDIT_ACCESS = False のためスキップしました")
    print("  → 07_audit_logs は講師が画面共有で説明する想定です")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 管理タグ（Governed Tag）3 種の作成
# MAGIC
# MAGIC ABAC の起点になるタグです。**アカウント全体で 1 つの定義を全参加者が共有**します。
# MAGIC
# MAGIC | タグキー | 許可値 | 用途 |
# MAGIC |---|---|---|
# MAGIC | `uc_handson_sensitivity` | `confidential` / `internal` / `public` | 列マスクの対象 |
# MAGIC | `uc_handson_domain` | `procurement` / `sales` | 行フィルタの判定列＋分類 |
# MAGIC | `uc_handson_layer` | `master` / `transaction` / `analytics` | データ層での分類 |
# MAGIC
# MAGIC > 既に存在する場合は「既に存在します」と表示されます（**正常**。作り直しは不要）。

# COMMAND ----------

governed_tags = [
    ("uc_handson_sensitivity",
     "CREATE GOVERNED TAG uc_handson_sensitivity "
     "DESCRIPTION 'Hands-on: column sensitivity level (drives column masking)' "
     "VALUES ('confidential','internal','public')"),
    ("uc_handson_domain",
     "CREATE GOVERNED TAG uc_handson_domain "
     "DESCRIPTION 'Hands-on: business domain of the asset (also drives row filtering)' "
     "VALUES ('procurement','sales')"),
    ("uc_handson_layer",
     "CREATE GOVERNED TAG uc_handson_layer "
     "DESCRIPTION 'Hands-on: data layer' "
     "VALUES ('master','transaction','analytics')"),
]

print("■ 管理タグの作成")
for tag, stmt in governed_tags:
    try:
        spark.sql(stmt)
        print(f"  ✓ 作成しました: {tag}")
        results.append(("ok", f"governed tag {tag}"))
    except Exception as e:
        msg = str(e)
        if "ALREADY_EXISTS" in msg or "already exists" in msg.lower():
            print(f"  ✓ 既に存在します: {tag}（そのまま使えます）")
            results.append(("ok", f"governed tag {tag} (existing)"))
        else:
            print(f"  ⚠️ {tag}")
            print(f"      → {msg.splitlines()[0][:180]}")
            print("      💡 管理タグの CREATE 権限が必要です"
                  "（アカウント管理者・ワークスペース管理者は既定で保有）")
            results.append(("ng", f"governed tag {tag}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. タグの ASSIGN 権限を参加者に付与（⚠️ 最重要）
# MAGIC
# MAGIC **`ASSIGN` が無いと参加者は `03_access_control` でタグを付与できません**（ハンズオンが止まります）。
# MAGIC タグを作成した人には `MANAGE` が自動で付きますが、**`ASSIGN` は別途付与が必要**です。
# MAGIC
# MAGIC ⚠️ **重要な制約**: 管理タグは**アカウントレベル**のリソースなので、
# MAGIC 付与先には**アカウントレベルのユーザー / グループ**を指定します。
# MAGIC カタログ権限で使えた `account users` や、ワークスペースローカルの `users` / `admins` は
# MAGIC **ここでは使えません**（`Group not found` になります）。
# MAGIC
# MAGIC そのため、下のセルで**参加者を明示的に指定**してください。

# COMMAND ----------

# ★★★ タグの ASSIGN を付与する相手（アカウントレベルのユーザー / グループ） ★★★
#
# 方法1: 参加者のメールアドレスを列挙する（確実）
TAG_ASSIGNEES = [
    # "taro.yamada@example.com",
    # "hanako.suzuki@example.com",
]
#
# 方法2: アカウントコンソールで作成したグループ名を 1 つ指定する（人数が多い場合に楽）
#        例: "uc_handson_participants"
#        ※ Account Console → User management → Groups で作成したグループのみ有効
TAG_ASSIGNEE_GROUP = ""

# COMMAND ----------

targets = [t for t in TAG_ASSIGNEES if t.strip()]
if TAG_ASSIGNEE_GROUP.strip():
    targets.append(TAG_ASSIGNEE_GROUP.strip())

assign_ok = True

if not targets:
    assign_ok = False
    print("⚠️ 付与先が未設定です（TAG_ASSIGNEES / TAG_ASSIGNEE_GROUP が空）")
    print("   上のセルに参加者のメールアドレス、またはアカウントグループ名を設定して再実行してください。")
    print()
    print("   ※ このまま当日を迎えると、参加者は 03 でタグを付与できません。")
else:
    print(f"■ ASSIGN 権限の付与（対象 {len(targets)} 件）")
    for tag, _ in governed_tags:
        for who in targets:
            try:
                spark.sql(f"GRANT ASSIGN ON GOVERNED TAG {tag} TO `{who}`")
                print(f"  ✓ ASSIGN on {tag} → {who}")
            except Exception as e:
                assign_ok = False
                msg = str(e).splitlines()[0]
                print(f"  ⚠️ ASSIGN on {tag} → {who}")
                print(f"      → {msg[:170]}")
                if "not found" in msg.lower() or "does not exist" in msg.lower():
                    print("      💡 アカウントレベルに存在する名前か確認してください"
                          "（ワークスペースローカルのグループは使えません）")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🖱️ UI で ASSIGN を付与する（SQL が使えない場合 / まとめて付与したい場合）
# MAGIC
# MAGIC 1. 左メニュー **Catalog** → 上部の **Govern**（盾アイコン）→ **Governed Tags**
# MAGIC 2. **まとめて付与**: **Account Permissions** → **Grant permissions**
# MAGIC    **タグ個別**: 対象タグ（`uc_handson_sensitivity` など）→ **Permissions** → **Grant permissions**
# MAGIC 3. 付与先（参加者またはアカウントグループ）を選択
# MAGIC 4. **ASSIGN** にチェック → 保存
# MAGIC
# MAGIC > 付与にはアカウントレベル、またはタグ個別の **MANAGE** 権限が必要です。
# MAGIC > 反映に 30 秒以上かかることがあります。
# MAGIC >
# MAGIC > 💡 **Account Permissions で一度付与すれば、以後作られるタグにも効きます**。
# MAGIC > 人数が多い場合や継続的に使う環境では、こちらが管理しやすいです。

# COMMAND ----------

print("■ 各タグの権限状況を確認")
for tag, _ in governed_tags:
    try:
        rows = spark.sql(f"SHOW GRANTS ON GOVERNED TAG {tag}").collect()
        print(f"\n  {tag}:")
        if rows:
            for r in rows:
                print(f"    - {r[0]} : {r[1]}")
        else:
            print("    （付与なし）")
    except Exception as e:
        print(f"\n  {tag}: 確認できません — {str(e).splitlines()[0][:120]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. 最終確認
# MAGIC
# MAGIC 付与された内容を一覧で確認します。

# COMMAND ----------

print("■ カタログの権限")
try:
    display(spark.sql(f"SHOW GRANTS ON CATALOG {TARGET_CATALOG}"))
except Exception as e:
    print("  ⚠️", str(e).splitlines()[0][:150])

# COMMAND ----------

print("■ メタストアの権限（CREATE SHARE / CREATE RECIPIENT があるか）")
try:
    display(spark.sql("SHOW GRANTS ON METASTORE"))
except Exception as e:
    print("  ⚠️", str(e).splitlines()[0][:150])

# COMMAND ----------

# MAGIC %md
# MAGIC ### 準備結果のまとめ

# COMMAND ----------

ng = [label for status, label in results if status == "ng"]

print("=" * 72)
if not ng and assign_ok:
    print("  ✅ 事前準備は完了しました")
    print("=" * 72)
    print(f"""
  参加者には次を伝えてください:

    ・ワークスペース URL
    ・Git リポジトリ URL（Workspace → Create → Git folder で取り込む）
    ・進行ガイド: HANDSON.md

  ⚠️ 権限とタグの反映に数分かかることがあります。
     当日の直前ではなく、余裕をもって確認してください。
""")
else:
    print(f"  ⚠️ {len(ng) + (0 if assign_ok else 1)} 件、未完了の項目があります")
    print("=" * 72)
    for label in ng:
        print(f"    - {label}")
    if not assign_ok:
        print("    - 管理タグの ASSIGN 付与（上の UI 手順を参照）")
    print("""
  対処のヒント:
    ・権限不足のもの → アカウント管理者 / メタストア管理者で再実行
    ・system.access が無い → アカウント設定で system スキーマを有効化
    ・ASSIGN が付与できない → 上に表示された UI 手順で付与
""")

print()
print("■ 次のステップ: 参加者と同じ権限のテストアカウントで")
print("  notebooks/core/00_setup 〜 08_genie を通し実行して確認してください。")
print("  （管理者アカウントでの成功は、参加者での成功を意味しません）")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 参考: このあと必要な確認・設定
# MAGIC
# MAGIC このノートブックで**自動化できない**項目です。画面から確認してください。
# MAGIC
# MAGIC | 項目 | 確認方法 |
# MAGIC |---|---|
# MAGIC | **参加者がログインできる** | Settings → Identity and access → Users に全員が登録されているか |
# MAGIC | **SQL Warehouse を使える** | Warehouse → Permissions に参加者が `CAN_USE` 以上で入っているか |
# MAGIC | **Serverless が使える** | ノートブックの **Connect** に Serverless が出るか |
# MAGIC | **AI 支援機能が有効**（`02` の AI コメント用） | 対象テーブルの Overview に **AI generate** が出るか |
# MAGIC | **`_config.py` のカタログ名** | `notebooks/core/_config.py` の `DEFAULT_CATALOG` が対象カタログか |
# MAGIC
# MAGIC ### （任意）ABAC の「両側」を見せたい場合
# MAGIC
# MAGIC `03` の行フィルタは「管理者は全件、営業は担当セグメントのみ」を想定しています。
# MAGIC **両側**を実演するには、アカウントに以下のグループを作成し、
# MAGIC 一部の参加者を所属させてください（**Account Console → User management → Groups**）。
# MAGIC
# MAGIC - `data_governance_admins` … 全件・実値が見える側
# MAGIC - `sales_automobile` / `sales_building` / `sales_machinery` … セグメント別に絞られる側
# MAGIC
# MAGIC > グループが無くても `03` は動きます。その場合、参加者は全員
# MAGIC > 「マスク・フィルタされる側」として制御が効く様子を観察できます。
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC 詳細な権限の一覧と背景は **`docs/permissions.md`** にまとめています。
