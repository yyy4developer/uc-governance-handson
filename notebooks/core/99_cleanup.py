# Databricks notebook source
# MAGIC %md
# MAGIC # 99 — 後片付け（ハンズオンで作ったものを削除）
# MAGIC
# MAGIC > 🔑 **必要な権限**: 削除対象の owner（自分が作ったものだけを消します）。
# MAGIC > 管理タグの削除は**アカウントレベルの権限**が必要（管理者向けの任意セル）
# MAGIC
# MAGIC ハンズオンで作成したリソースを**一括削除**します。
# MAGIC
# MAGIC ## 削除されるもの
# MAGIC
# MAGIC | 対象 | 内容 | スコープ |
# MAGIC |---|---|---|
# MAGIC | ABAC ポリシー | 列マスク・行フィルタ | 自分のスキーマ |
# MAGIC | マスク/フィルタ関数 | `mask_confidential_value` など | 自分のスキーマ |
# MAGIC | Delta Share / Recipient | `order_analysis_share_<自分>` など | メタストア（自分のもののみ） |
# MAGIC | **スキーマごと削除** | テーブル・ビュー・Volume すべて | 自分のスキーマ |
# MAGIC | 他者への GRANT | `03` で参加者グループに付与した権限 | 自分のスキーマ |
# MAGIC
# MAGIC ## ⚠️ 削除されないもの（意図的）
# MAGIC
# MAGIC - **管理タグ（Governed Tag）**: アカウント全体で共有されるため、
# MAGIC   他の参加者がまだ使っている可能性があります。最後の任意セルで個別に削除できます。
# MAGIC - **カタログ**: 管理者が用意したものなので触りません。
# MAGIC - **他の参加者のスキーマ**: 自分のものだけを削除します。
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ⚠️ **この操作は取り消せません。** 実行前に、削除対象が自分のスキーマであることを確認してください。

# COMMAND ----------

# MAGIC %run ./_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 削除対象の確認（まずここを実行）
# MAGIC
# MAGIC **何が削除されるか**を先に一覧表示します。この時点では何も削除されません。

# COMMAND ----------

print("=" * 70)
print(f"  削除対象スキーマ: {FQ}")
print(f"  実行ユーザー    : {spark.sql('SELECT current_user()').collect()[0][0]}")
print("=" * 70)
print()

# テーブル・ビュー
try:
    objs = spark.sql(f"SHOW TABLES IN {FQ}").collect()
    print(f"■ テーブル / ビュー（{len(objs)} 件）")
    for o in objs:
        print(f"    - {o['tableName']}")
except Exception as e:
    print("■ テーブル: 取得できませんでした（スキーマが無い可能性）")
    print(f"    {str(e).splitlines()[0][:120]}")
print()

# Volume
try:
    vols = spark.sql(f"SHOW VOLUMES IN {FQ}").collect()
    print(f"■ Volume（{len(vols)} 件）")
    for v in vols:
        print(f"    - {v[1] if len(v) > 1 else v[0]}")
except Exception:
    print("■ Volume: なし")
print()

# ABAC ポリシー
try:
    pols = spark.sql(f"SHOW POLICIES ON SCHEMA {FQ}").collect()
    print(f"■ ABAC ポリシー（{len(pols)} 件）")
    for p in pols:
        print(f"    - {p[0]}")
except Exception:
    print("■ ABAC ポリシー: なし")
print()

# 関数
try:
    funcs = spark.sql(f"SHOW USER FUNCTIONS IN {FQ}").collect()
    print(f"■ 関数（{len(funcs)} 件）")
    for f in funcs:
        print(f"    - {f[0]}")
except Exception:
    print("■ 関数: なし")

# COMMAND ----------

# 自分の Delta Share / Recipient
user = spark.sql("SELECT current_user()").collect()[0][0]
user_token = user.split("@")[0].replace(".", "_").replace("-", "_").lower()

print(f"■ Delta Share / Recipient（識別子: {user_token}）")
for kind in ["SHARES", "RECIPIENTS"]:
    try:
        rows = spark.sql(f"SHOW {kind}").collect()
        mine = [r[0] for r in rows if user_token in str(r[0])]
        print(f"  {kind}: {mine if mine else '(自分のものはなし)'}")
    except Exception as e:
        print(f"  {kind}: 一覧を取得できません（{str(e).splitlines()[0][:80]}）")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 実行の確認
# MAGIC
# MAGIC 上の一覧が**自分のもの**であることを確認したら、次のセルで `CONFIRM = True` に変更してください。
# MAGIC `False` のままだと削除は実行されません（安全のため既定は `False`）。

# COMMAND ----------

# ★ 削除を実行する場合は True に変更してください
CONFIRM = False

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 削除の実行
# MAGIC
# MAGIC `CONFIRM = True` にしてから実行してください。

# COMMAND ----------


def step(stmt: str, label: str):
    """1 文を実行。失敗しても止めずに理由を表示する"""
    try:
        spark.sql(stmt)
        print(f"  ✓ {label}")
        return True
    except Exception as e:
        msg = str(e).splitlines()[0]
        # 「存在しない」系は正常（既に消えている / そもそも作っていない）
        if any(k in msg for k in ("NOT_FOUND", "does not exist", "DOES_NOT_EXIST",
                                  "SCHEMA_NOT_FOUND", "TABLE_OR_VIEW_NOT_FOUND",
                                  "PRINCIPAL_DOES_NOT_EXIST")):
            print(f"  · スキップ（存在しません）: {label}")
        else:
            print(f"  ⚠️ {label}\n      → {msg[:150]}")
        return False


if not CONFIRM:
    print("CONFIRM = False のため、何も削除していません。")
    print("削除するには上のセルで CONFIRM = True にしてから再実行してください。")
else:
    print(f"■ {FQ} のクリーンアップを開始します\n")

    # --- 3-1. ABAC ポリシーを外す（スキーマ削除より先に） ---
    print("[1/5] ABAC ポリシーの削除")
    for pol in ["mask_confidential_columns", "filter_rows_by_domain"]:
        step(f"DROP POLICY {pol} ON SCHEMA {FQ}", f"ポリシー {pol}")

    # --- 3-2. 他者に付与した権限を取り消す（03 の RBAC 演習で付与したもの） ---
    print("\n[2/5] 他者への GRANT を取り消し")
    try:
        grants = spark.sql(f"SHOW GRANTS ON SCHEMA {FQ}").collect()
        me = spark.sql("SELECT current_user()").collect()[0][0]
        # このスキーマに直接付与されている principal のみ（カタログ由来の行は除く）
        others = {
            g[0] for g in grants
            if g[0] and g[0] != me
            and str(g[3]).endswith(schema)          # 対象がこのスキーマの付与だけ
            and "admin" not in str(g[0]).lower()
        }
        others.add(PARTICIPANT_GROUP)               # 03 で付与したグループは明示的に対象
        for principal in sorted(others):
            step(f"REVOKE ALL PRIVILEGES ON SCHEMA {FQ} FROM `{principal}`",
                 f"{principal} からの権限")
    except Exception as e:
        print(f"  · 確認できませんでした: {str(e).splitlines()[0][:100]}")

    # --- 3-3. Delta Share / Recipient ---
    print("\n[3/5] Delta Share / Recipient の削除")
    for kind, singular in [("SHARES", "SHARE"), ("RECIPIENTS", "RECIPIENT")]:
        try:
            rows = spark.sql(f"SHOW {kind}").collect()
            mine = [r[0] for r in rows if user_token in str(r[0])]
            if mine:
                for name in mine:
                    step(f"DROP {singular} `{name}`", f"{singular} {name}")
            else:
                print(f"  · 自分の {singular} はありません")
        except Exception as e:
            print(f"  · {kind}: {str(e).splitlines()[0][:100]}")

    # --- 3-4. スキーマごと削除（テーブル・ビュー・Volume・関数すべて） ---
    print("\n[4/5] スキーマの削除（配下すべて）")
    step(f"DROP SCHEMA IF EXISTS {FQ} CASCADE", f"スキーマ {FQ}")

    # --- 3-5. 確認 ---
    print("\n[5/5] 確認")
    try:
        left = spark.sql(f"SHOW SCHEMAS IN {catalog} LIKE '{schema}'").collect()
        if left:
            print(f"  ⚠️ スキーマがまだ残っています: {left}")
        else:
            print(f"  ✓ {FQ} は削除されました")
    except Exception as e:
        print(f"  · 確認できませんでした: {str(e).splitlines()[0][:100]}")

    print("\n■ クリーンアップ完了")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4.（任意・管理者向け）管理タグの削除
# MAGIC
# MAGIC 管理タグは**アカウント全体で共有**されるため、上の処理では削除していません。
# MAGIC **全参加者のクリーンアップが終わったあと**、管理者が最後に実行してください。
# MAGIC
# MAGIC ⚠️ 他の参加者がまだタグを使っている状態で削除すると、その人の環境に影響します。
# MAGIC ⚠️ 列やテーブルにタグが付いたまま削除すると、タグは「通常タグ」に降格して残ります
# MAGIC （スキーマごと削除していれば影響ありません）。

# COMMAND ----------

# ★ 管理タグも削除する場合は True に変更（全参加者の完了後、管理者のみ）
DROP_GOVERNED_TAGS = False

# COMMAND ----------

if not DROP_GOVERNED_TAGS:
    print("DROP_GOVERNED_TAGS = False のため、管理タグは残しています。")
    print("削除する場合は上のセルで True にしてください（全参加者の完了後に）。")
else:
    print("■ 管理タグを削除します\n")
    for tag in ["uc_handson_sensitivity", "uc_handson_domain", "uc_handson_layer"]:
        try:
            spark.sql(f"DROP GOVERNED TAG {tag}")
            print(f"  ✓ {tag}")
        except Exception as e:
            msg = str(e).splitlines()[0]
            if "NOT_FOUND" in msg or "does not exist" in msg:
                print(f"  · スキップ（存在しません）: {tag}")
            else:
                print(f"  ⚠️ {tag}: {msg[:150]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. 手動で確認・削除するもの（UI 操作）
# MAGIC
# MAGIC 以下は SQL で消せないため、必要なら画面から操作してください。
# MAGIC
# MAGIC | 対象 | 操作 |
# MAGIC |---|---|
# MAGIC | **Genie スペース**（`08` で作成） | 左メニュー **Genie** → 対象スペース → **⋮ → Delete** |
# MAGIC | **Git folder**（取り込んだリポジトリ） | **Workspace** → `uc-governance-handson` → **⋮ → Delete** |
# MAGIC | **ダッシュボード**（`07` で任意作成した場合） | **Dashboards** → 対象 → **⋮ → Move to trash** |
# MAGIC
# MAGIC 管理者が確認するもの:
# MAGIC
# MAGIC - **参加者全員のスキーマが消えたか**: Catalog → カタログ配下に `uc_handson_*` が残っていないか
# MAGIC - **ワークスペース自体**: 検証用に作った環境なら、不要になった時点で削除
