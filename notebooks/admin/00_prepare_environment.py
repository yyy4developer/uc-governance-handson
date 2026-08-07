# Databricks notebook source
# MAGIC %md
# MAGIC # 管理者向け — ハンズオン環境の事前準備（これ1本で完了）
# MAGIC
# MAGIC > 🔑 **実行できる人**: **アカウント管理者**
# MAGIC > （グループ作成・`system.access` の付与・管理タグの権限付与に必要）
# MAGIC
# MAGIC ハンズオン当日までに必要な準備を、**このノートブック 1 本**で実施します。
# MAGIC
# MAGIC ## 方針: 専用グループを作り、権限は全部グループ単位で付与
# MAGIC
# MAGIC 参加者を 1 人ずつ指定するのは手間で、抜け漏れも起きます。
# MAGIC **一時的な参加者グループを作り、権限はすべてそのグループに付与**します。
# MAGIC 終了後はグループを削除すれば、付与した権限もまとめて無効化できます。
# MAGIC
# MAGIC | # | 内容 | 実行場所 |
# MAGIC |---|---|---|
# MAGIC | 1 | 前提チェック（カタログ / `samples` / `system.access`） | このnotebook |
# MAGIC | 2 | **参加者グループの作成 + ワークスペース割り当て** | ⚠️ **Account Console**（手動） |
# MAGIC | 3 | **グループへの権限付与**（カタログ / メタストア / 監査ログ） | このnotebook |
# MAGIC | 4 | **管理タグ 3 種の作成** ＋ **グループに ASSIGN 付与** | このnotebook |
# MAGIC | 5 | 最終確認 | このnotebook |
# MAGIC
# MAGIC > ⚠️ **§2 だけは Account Console での手動作業です**。アカウントレベルのグループ操作は
# MAGIC > notebook から実行できないためです（手順は §2 に記載）。それ以外は自動で実行されます。
# MAGIC
# MAGIC ## 使い方
# MAGIC
# MAGIC 1. 下の **設定** セルで `TARGET_CATALOG` と `GROUP_NAME` を確認
# MAGIC 2. **▶ Run all** で実行 → §2 でグループ未作成なら止まるので、表示された手順で作成
# MAGIC 3. グループを作ったら**もう一度 ▶ Run all**（冪等なので何度でも実行できます）
# MAGIC 4. 出力の ✓ / ⚠️ を確認（⚠️ には対処方法が表示されます）
# MAGIC
# MAGIC > 💡 **参加者のメールアドレスはこのノートブックに書きません。**
# MAGIC > メンバーの追加は Account Console 側で行い、権限はすべてグループに対して付与します
# MAGIC > （このリポジトリに個人情報を残さないためでもあります）。
# MAGIC
# MAGIC > ⚠️ **前日までに実行してください**。グループ・権限・タグの反映に**数分**かかることがあります。
# MAGIC >
# MAGIC > 💡 参加者が作業する `notebooks/core/` は触りません。このノートブックは環境準備専用です。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 設定（ここだけ書き換えてください）

# COMMAND ----------

# ★★★ 1. 対象カタログ名（参加者がスキーマを作るカタログ） ★★★
TARGET_CATALOG = "main"

# ★★★ 2. 参加者グループ名 ★★★
#   Account Console で作成したグループ名（§2 参照）。
#   参加者の追加は Account Console 側で行うため、ここにメールアドレスは書きません。
#   ⚠️ notebooks/core/_config.py の PARTICIPANT_GROUP と同じ値にしてください
GROUP_NAME = "trail-uc-handson-grp"

# ★★★ 3. 監査ログ（07）を参加者に実行させるか ★★★
#   True  → system.access に SELECT を付与
#           ⚠️ 参加者はアカウント全体の監査ログを読めるようになります
#   False → 付与しない（07 は講師が画面共有で説明）
GRANT_AUDIT_ACCESS = True

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 前提チェック
# MAGIC
# MAGIC 実行前に、満たしていない前提がないかを確認します。

# COMMAND ----------

import json

warn = []


def check(label: str, fn):
    try:
        result = fn()
        if result is True:
            print(f"  ✓ {label}")
        else:
            warn.append(label)
            print(f"  ⚠️ {label} — {result}")
    except Exception as e:
        warn.append(label)
        print(f"  ⚠️ {label} — {str(e).splitlines()[0][:160]}")


me = spark.sql("SELECT current_user()").collect()[0][0]

print(f"実行ユーザー  : {me}")
print(f"対象カタログ  : {TARGET_CATALOG}")
print(f"参加者グループ: {GROUP_NAME}")
print()

print("■ 前提チェック")
check(f"カタログ {TARGET_CATALOG} が存在する",
      lambda: True if spark.sql(f"SHOW CATALOGS LIKE '{TARGET_CATALOG}'").collect()
      else f"'{TARGET_CATALOG}' が見つかりません（名前を確認してください）")
check("カタログの権限を参照できる（owner / MANAGE）",
      lambda: bool(spark.sql(f"SHOW GRANTS ON CATALOG {TARGET_CATALOG}").collect()) or True)
check("samples.tpch が読める",
      lambda: True if spark.sql("SELECT count(*) FROM samples.tpch.customer").collect()[0][0] > 0
      else "samples.tpch.customer が空です")
if GRANT_AUDIT_ACCESS:
    check("system.access.audit が有効",
          lambda: bool(spark.sql("SELECT 1 FROM system.access.audit LIMIT 1").collect()) or True)

print()
print(f"{'⚠️ ' + str(len(warn)) + ' 件の確認事項があります' if warn else '✓ 前提はすべて満たしています'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 参加者グループの準備（⚠️ ここだけ Account Console で手動作業）
# MAGIC
# MAGIC ### なぜ手動なのか
# MAGIC
# MAGIC Unity Catalog の権限は**アカウントレベルのグループ**にしか付与できません。
# MAGIC そして**アカウントレベルの操作は notebook からは実行できません**
# MAGIC （notebook はワークスペースの資格情報で動くため、アカウント API に到達できません）。
# MAGIC
# MAGIC | 作り方 | UC 権限に使えるか | notebook から可能か |
# MAGIC |---|---|---|
# MAGIC | SQL の `CREATE GROUP` | ❌ **使えません**（ワークスペースローカルになる） | ○ |
# MAGIC | **Account Console** | ✅ 使える | ✗ |
# MAGIC | Databricks CLI（account profile） | ✅ 使える | ✗ |
# MAGIC
# MAGIC ### 手順（5 分程度）
# MAGIC
# MAGIC **A. アカウントレベルでグループを作成し、参加者を追加**
# MAGIC
# MAGIC 1. [Account Console](https://accounts.cloud.databricks.com) にログイン
# MAGIC    （Azure: `https://accounts.azuredatabricks.net`）
# MAGIC 2. **User management** → **Groups** → **Add group**
# MAGIC 3. グループ名に下のセルで表示される名前を入力 → **Confirm**
# MAGIC 4. 作成したグループを開き → **Members** → **Add members** → 参加者を選択
# MAGIC
# MAGIC **B. ⚠️ このワークスペースに追加する（これを忘れると権限付与が失敗します）**
# MAGIC
# MAGIC アカウントに作っただけでは、**このワークスペースの SQL から認識されません**。
# MAGIC 次のいずれかで追加してください。
# MAGIC
# MAGIC *方法1: ワークスペースの設定画面から（かんたん・推奨）*
# MAGIC
# MAGIC 1. このワークスペースの右上 **⚙ Settings** → **Identity and access**
# MAGIC 2. **Groups** の **Manage**（または **Add group**）
# MAGIC 3. **A** で作ったグループ名を検索して選択 → **Add**
# MAGIC
# MAGIC *方法2: Account Console から*
# MAGIC
# MAGIC 1. Account Console → **Workspaces** → 対象ワークスペースを開く
# MAGIC 2. グループを検索して選択し、ワークスペースの entitlement を付けて **Save**
# MAGIC    （画面構成はアカウントの設定により異なります。見つからない場合は方法1 を使ってください）
# MAGIC
# MAGIC > ⚠️ **B を実施しないと** SQL から `Principal ... does not exist` になります。
# MAGIC > グループは存在するのに認識されない、という分かりにくい失敗をします。
# MAGIC > 追加直後は反映に**数十秒**かかります。
# MAGIC
# MAGIC ### CLI で行う場合（管理者の PC から。上記 A + B と同じこと）
# MAGIC
# MAGIC ```bash
# MAGIC # 1) アカウントプロファイルで認証（初回のみ）
# MAGIC databricks auth login --host <account-console-url> --account-id <account-id>
# MAGIC
# MAGIC # 2) アカウントにグループを作成
# MAGIC databricks account groups create --display-name trail-uc-handson-grp \
# MAGIC   -p <account-profile>
# MAGIC
# MAGIC # 3) このワークスペースに追加（同名で POST する。ワークスペースのプロファイルで実行）
# MAGIC databricks api post /api/2.0/preview/scim/v2/Groups -p <workspace-profile> \
# MAGIC   --json '{"displayName":"trail-uc-handson-grp",
# MAGIC            "schemas":["urn:ietf:params:scim:schemas:core:2.0:Group"]}'
# MAGIC ```
# MAGIC
# MAGIC > 💡 3) は「アカウントのグループをこのワークスペースから使えるようにする」操作です
# MAGIC > （方法1 の UI と同じことをしています）。**2) を省いて 3) だけ実行すると
# MAGIC > ワークスペースローカルのグループになり、UC の権限付与に使えません。**

# COMMAND ----------

# グループの準備状況を確認する（作成されワークスペースに割り当てられているか）
# ※ 表示用のワークスペース ID 取得やメンバー一覧は SDK 経由で失敗することがあるが、
#   いずれも「確認のための補助情報」なので、失敗してもこの先の権限付与は続行する。
try:
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
except Exception as e:
    w = None
    print("· SDK クライアントを初期化できませんでした（メンバー確認はスキップします）:",
          str(e).splitlines()[0][:120])

ws_id = "(取得できません)"
try:
    if w is not None:
        ws_id = w.get_workspace_id()
except Exception:
    # get_workspace_id は内部で getMe を呼ぶため環境によって失敗するが、表示用なので無視
    pass

print("=" * 72)
print(f"  参加者グループ名   : {GROUP_NAME}")
print(f"  対象ワークスペース : id={ws_id}")
print("=" * 72)
print()

group_ready = False
try:
    rows = spark.sql(f"SHOW GROUPS LIKE '{GROUP_NAME}'").collect()
    if rows:
        group_ready = True
        print(f"✓ グループ '{GROUP_NAME}' はワークスペースから認識されています")
        # メンバーを確認（メールアドレスをこのファイルに書かず、実際の登録内容を読み取る）
        try:
            if w is None:
                raise RuntimeError("SDK クライアント未初期化")
            found = list(w.groups.list(filter=f'displayName eq "{GROUP_NAME}"'))
            members = found[0].members if found and found[0].members else []
            print(f"  メンバー: {len(members)} 名")
            for m in members:
                print(f"      - {m.display}")
            if not members:
                print("  ⚠️ メンバーが 0 名です — Account Console で参加者を追加してください")
        except Exception as ex:
            print(f"  · メンバー一覧を取得できません: {str(ex).splitlines()[0][:120]}")
            print("    → Account Console → Groups → 対象グループ → Members で確認してください")
    else:
        print(f"⚠️ グループ '{GROUP_NAME}' が見つかりません")
        print()
        print("   上の手順 A・B を実施してから、このセルを再実行してください。")
        print("   （B のワークスペース割り当てが未実施でも、この確認は失敗します）")
except Exception as e:
    print("⚠️ 確認できません:", str(e).splitlines()[0][:150])

if not group_ready:
    print()
    print("   ⛔ グループが未準備のため、この先の権限付与は失敗します。")
    print("      グループを用意してから続行してください。")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. グループへの権限付与
# MAGIC
# MAGIC | 付与内容 | 使う notebook |
# MAGIC |---|---|
# MAGIC | `USE CATALOG` + `CREATE SCHEMA`（カタログ） | `00`〜`05`（自分のスキーマを作る） |
# MAGIC | `CREATE SHARE` + `CREATE RECIPIENT`（メタストア） | `06`（Delta Sharing） |
# MAGIC | `USE SCHEMA` + `SELECT`（`system.access`） | `07`（監査ログ）※ 任意 |
# MAGIC
# MAGIC ### ⛔ カタログに `SELECT` や `USE SCHEMA` を付けないでください
# MAGIC
# MAGIC 「参加者が困らないように」と、対象カタログに次を付けたくなるかもしれません。
# MAGIC
# MAGIC ```sql
# MAGIC -- ❌ これをやると 03 の RBAC 演習が成立しなくなります
# MAGIC GRANT USE SCHEMA, SELECT ON CATALOG <catalog> TO `<group>`;
# MAGIC ```
# MAGIC
# MAGIC UC の権限は **カタログ → スキーマ → テーブル**に継承されます。カタログに `SELECT` を付けると
# MAGIC **参加者全員が互いのテーブルを最初から読めてしまい**、`03` の
# MAGIC 「付与前は読めない → 付与すると読める → REVOKE で読めなくなる」という
# MAGIC 体験ができなくなります。
# MAGIC
# MAGIC 参加者は自分で作ったスキーマの **owner** になるので、
# MAGIC **`USE CATALOG` + `CREATE SCHEMA` だけで `00`〜`05` は問題なく実行できます**
# MAGIC （必要十分。これ以上は付けない）。

# COMMAND ----------

failed = []


def grant(stmt: str, label: str, hint: str = ""):
    try:
        spark.sql(stmt)
        print(f"  ✓ {label}")
    except Exception as e:
        msg = str(e).splitlines()[0]
        failed.append(label)
        print(f"  ⚠️ {label}")
        print(f"      → {msg[:180]}")
        if "does not exist" in msg or "not found" in msg.lower():
            print("      💡 グループがワークスペースに割り当てられているか確認してください"
                  "（割り当て直後は反映に数十秒かかります）")
        elif hint:
            print(f"      💡 {hint}")


G = f"`{GROUP_NAME}`"

print("■ カタログ（自分のスキーマを作れるようにする）")
grant(f"GRANT USE CATALOG, CREATE SCHEMA ON CATALOG {TARGET_CATALOG} TO {G}",
      f"USE CATALOG + CREATE SCHEMA on {TARGET_CATALOG}",
      "カタログの owner または MANAGE 権限が必要です")

print("\n■ メタストア（Delta Sharing / 06 で使用）")
grant(f"GRANT CREATE SHARE, CREATE RECIPIENT ON METASTORE TO {G}",
      "CREATE SHARE + CREATE RECIPIENT on METASTORE",
      "メタストア管理者またはアカウント管理者で実行してください")

if GRANT_AUDIT_ACCESS:
    print("\n■ 監査ログ（system.access / 07 で使用）")
    print("  ⚠️ 参加者はアカウント全体の監査ログを読めるようになります")
    grant(f"GRANT USE SCHEMA, SELECT ON SCHEMA system.access TO {G}",
          "USE SCHEMA + SELECT on system.access",
          "アカウント管理者で実行してください（system スキーマの有効化も必要）")
else:
    print("\n■ 監査ログ: GRANT_AUDIT_ACCESS = False のためスキップ")
    print("  → 07_audit_logs は講師が画面共有で説明する想定です")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. 管理タグ 3 種の作成と ASSIGN 付与
# MAGIC
# MAGIC ABAC の起点になるタグです。**アカウント全体で 1 つの定義を全参加者が共有**します。
# MAGIC
# MAGIC | タグキー | 許可値 | 用途 |
# MAGIC |---|---|---|
# MAGIC | `uc_handson_sensitivity` | `confidential` / `internal` / `public` | 列マスクの対象 |
# MAGIC | `uc_handson_domain` | `procurement` / `sales` | 行フィルタの判定列＋分類 |
# MAGIC | `uc_handson_layer` | `master` / `transaction` / `analytics` | データ層での分類 |
# MAGIC
# MAGIC ⚠️ **`ASSIGN` が無いと参加者は `03` でタグを付与できません**（ハンズオンが止まります）。
# MAGIC タグ作成者には `MANAGE` が自動で付きますが、`ASSIGN` は別途付与が必要です。

# COMMAND ----------

governed_tags = [
    ("uc_handson_sensitivity",
     "CREATE GOVERNED TAG uc_handson_sensitivity "
     "DESCRIPTION '機微度（列マスクの対象を決める）' "
     "VALUES ('confidential','internal','public')"),
    ("uc_handson_domain",
     "CREATE GOVERNED TAG uc_handson_domain "
     "DESCRIPTION '業務ドメイン（行フィルタの判定にも使用）' "
     "VALUES ('procurement','sales')"),
    ("uc_handson_layer",
     "CREATE GOVERNED TAG uc_handson_layer "
     "DESCRIPTION 'データ層（マスタ / トランザクション / 分析）' "
     "VALUES ('master','transaction','analytics')"),
]

print("■ 管理タグの作成")
for tag, stmt in governed_tags:
    try:
        spark.sql(stmt)
        print(f"  ✓ 作成しました: {tag}")
    except Exception as e:
        msg = str(e)
        if "ALREADY_EXISTS" in msg or "already exists" in msg.lower():
            print(f"  ✓ 既に存在します: {tag}（そのまま使えます）")
        else:
            failed.append(f"governed tag {tag}")
            print(f"  ⚠️ {tag} → {msg.splitlines()[0][:180]}")
            print("      💡 管理タグの CREATE 権限が必要です"
                  "（アカウント管理者・ワークスペース管理者は既定で保有）")

print("\n■ ASSIGN 権限の付与（グループ単位）")
for tag, _ in governed_tags:
    grant(f"GRANT ASSIGN ON GOVERNED TAG {tag} TO {G}", f"ASSIGN on {tag} → {GROUP_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 🖱️ UI で ASSIGN を付与する（SQL が失敗した場合）
# MAGIC
# MAGIC 1. 左メニュー **Catalog** → 上部の **Govern**（盾アイコン）→ **Governed Tags**
# MAGIC 2. **まとめて付与**: **Account Permissions** → **Grant permissions**
# MAGIC    **タグ個別**: 対象タグ → **Permissions** → **Grant permissions**
# MAGIC 3. 付与先に参加者グループを選択
# MAGIC 4. **ASSIGN** にチェック → 保存
# MAGIC
# MAGIC > 💡 **Account Permissions で付与すれば、以後作られるタグにも効きます**。
# MAGIC > 継続的に使う環境ではこちらが管理しやすいです。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. 最終確認

# COMMAND ----------

print("■ 管理タグの権限")
for tag, _ in governed_tags:
    try:
        rows = spark.sql(f"SHOW GRANTS ON GOVERNED TAG {tag}").collect()
        holders = [f"{r[0]}:{r[1]}" for r in rows]
        has_assign = any(r[0] == GROUP_NAME and r[1] == "ASSIGN" for r in rows)
        mark = "✓" if has_assign else "⚠️"
        print(f"  {mark} {tag}")
        for h in holders:
            print(f"      {h}")
        if not has_assign:
            print(f"      → {GROUP_NAME} に ASSIGN がありません（上の UI 手順で付与してください）")
    except Exception as e:
        print(f"  ⚠️ {tag}: {str(e).splitlines()[0][:130]}")

# COMMAND ----------

print("■ カタログの権限")
display(spark.sql(f"SHOW GRANTS ON CATALOG {TARGET_CATALOG}"))

# COMMAND ----------

print("■ メタストアの権限")
display(spark.sql("SHOW GRANTS ON METASTORE"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 準備結果のまとめ

# COMMAND ----------

print("=" * 72)
if not failed:
    print("  ✅ 事前準備は完了しました")
    print("=" * 72)
    print(f"""
  作成したもの:
    ・管理タグ 3 種（ASSIGN をグループ {GROUP_NAME} に付与）
    ・カタログ / メタストア / 監査ログの権限（すべてグループ単位）

  ⚠️ notebooks/core/_config.py の PARTICIPANT_GROUP が
     "{GROUP_NAME}" になっているか確認してください
     （03 の RBAC 演習でこのグループに GRANT します）

  参加者に伝えること:
    ・ワークスペース URL
    ・Git リポジトリ URL（Workspace → Create → Git folder で取り込む）
    ・進行ガイド: HANDSON.md

  ⚠️ グループメンバーシップと権限の反映に数分かかります。
     当日直前ではなく、余裕をもって確認してください。
""")
else:
    print(f"  ⚠️ {len(failed)} 件、未完了の項目があります")
    print("=" * 72)
    for label in failed:
        print(f"    - {label}")
    print("""
  対処のヒント:
    ・「does not exist」→ グループのワークスペース割り当てを確認（反映に数十秒）
    ・権限不足 → アカウント管理者 / メタストア管理者で再実行
    ・system.access が無い → アカウント設定で system スキーマを有効化
    ・ASSIGN が付与できない → 上の UI 手順で付与
""")

print()
print("■ 次のステップ（強く推奨）")
print("  参加者と同じ権限のテストアカウントで notebooks/core/00_setup 〜 08_genie を")
print("  通し実行してください。管理者アカウントでの成功は参加者での成功を意味しません。")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 参考: このノートブックで自動化できないもの
# MAGIC
# MAGIC | 項目 | 確認方法 |
# MAGIC |---|---|
# MAGIC | **参加者がアカウントに登録済み** | Account Console → User management → Users |
# MAGIC | **SQL Warehouse を使える** | Warehouse → Permissions に参加者グループが `CAN_USE` 以上 |
# MAGIC | **Serverless が使える** | ノートブックの **Connect** に Serverless が出るか |
# MAGIC | **AI 支援機能が有効**（`02` の AI コメント用） | テーブルの Overview に **AI generate** が出るか |
# MAGIC | **`_config.py` のカタログ名** | `notebooks/core/_config.py` の `DEFAULT_CATALOG` |
# MAGIC
# MAGIC 💡 SQL Warehouse の権限も、作成した参加者グループに付与すると管理が楽です
# MAGIC （Warehouse → **Permissions** → グループを追加 → `CAN_USE`）。
# MAGIC
# MAGIC ### （任意）ABAC の「両側」を見せたい場合
# MAGIC
# MAGIC `03` の行フィルタは「管理者は全件、営業は担当セグメントのみ」を想定しています。
# MAGIC 両側を実演するには、以下のグループをアカウントに作成し、一部の参加者を所属させてください。
# MAGIC
# MAGIC - `data_governance_admins` … 全件・実値が見える側
# MAGIC - `sales_automobile` / `sales_building` / `sales_machinery` … セグメント別に絞られる側
# MAGIC
# MAGIC > グループが無くても `03` は動きます。その場合、参加者は全員
# MAGIC > 「マスク・フィルタされる側」として制御が効く様子を観察できます。
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 🧹 ハンズオン終了後の片付け
# MAGIC
# MAGIC 1. 参加者が各自 `notebooks/core/99_cleanup` を実行（自分のスキーマ等を削除）
# MAGIC 2. 管理者が `notebooks/admin/01_cleanup_environment` を実行
# MAGIC    （グループ削除 = 付与した権限もまとめて無効化、管理タグ削除）
# MAGIC
# MAGIC 詳細な権限の一覧と背景は **`docs/permissions.md`** にまとめています。
