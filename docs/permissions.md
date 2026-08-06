# ハンズオン実施に必要な権限リスト

参加者が `notebooks/core/00`〜`08` を最後まで実行するために必要な権限をまとめたものです。
**ワークスペース環境の管理者（account admin / workspace admin）が事前に準備**してください。

> 📌 **役割分担**: 環境の準備・権限付与・管理タグの作成は**管理者**が行います。
> 講師は進行と説明を担当し、環境操作は行いません（クライアント環境にアクセスできない前提）。

- 付与は **SQL Editor** から実行できます（一部は Catalog Explorer の UI 操作）
- 反映に**数分**かかることがあります。**当日ではなく前日までに**済ませてください
- `<catalog>` は `_config.py` の `DEFAULT_CATALOG` に設定したカタログ名に読み替えてください

> ⭐ **権限はすべて「参加者グループ」単位で付与します。** 個人のメールアドレスを列挙する方法は
> 取りません（付け忘れ・片付け漏れが起きるうえ、実運用の作法でもありません）。
> 本ドキュメントの `<group>` は、Account Console で作成した参加者グループ名
> （既定 `uc_handson_participants`）に読み替えてください。
>
> ⚠️ グループは **Account Console で作成**し、**さらにこのワークスペースに追加**する必要があります。
> SQL の `CREATE GROUP` で作るとワークスペースローカルになり、UC の権限付与に使えません
> （`PRINCIPAL_DOES_NOT_EXIST` になります）。

> ⛔ **カタログに `SELECT` / `USE SCHEMA` を付けないでください。**
> UC の権限はカタログ → スキーマ → テーブルに継承されるため、
> 付けると参加者全員が互いのテーブルを最初から読めてしまい、
> `03` の RBAC 演習（付与前は読めない → 付与で読める → REVOKE で読めなくなる）が
> 成立しなくなります。`USE CATALOG` + `CREATE SCHEMA` で必要十分です
> （参加者は自分のスキーマの owner になります）。

---

## 0. 前提（これが無いと何も始まりません）

| # | 項目 | 確認方法 |
|---|---|---|
| 0-1 | **参加者がワークスペースにログインできる** | Settings → Identity and access → Users に参加者が登録されているか |
| 0-2 | **参加者が SQL Warehouse を使える** | Warehouse の Permissions に `users` または参加者が `CAN_USE` 以上で入っているか |
| 0-3 | **Serverless コンピュートが使える** | ノートブックの **Connect** に Serverless が出るか |
| 0-4 | **`samples` カタログが見える** | `SELECT count(*) FROM samples.tpch.customer` が通るか（権限設定は不要） |

---

## ⭐ 一括実行する方法（推奨）

**権限はすべて「参加者グループ」単位で付与します。** 個人ごとの付与より確実で、
終了後はグループを削除すれば全権限がまとめて無効化されます。

1. **グループを用意**（手動、5分）
   - **Account Console** → User management → Groups → **Add group** → 参加者を Members に追加
   - ⚠️ **このワークスペースに追加**: ワークスペースの **⚙ Settings** →
     **Identity and access** → **Groups** → **Add group** → 作ったグループを選択
2. **`notebooks/admin/00_prepare_environment` を実行** — §1〜§2 の内容
   （権限付与・管理タグ作成・ASSIGN 付与）がまとめて実施されます

⚠️ **1 だけは手動**です。アカウントレベルのグループ操作は notebook から実行できません
（notebook はワークスペースの資格情報で動くため）。

⚠️ **アカウントに作る + ワークスペースに追加の両方が必要です。**
片方だけでは SQL から `Principal ... does not exist` になります
（ワークスペースにだけ作るとローカルグループになり、UC では使えません）。

片付けは **`notebooks/admin/01_cleanup_environment`**（参加者の `99_cleanup` のあと）。

以下は、その内容の詳細と、手動で実施する場合の手順です。

---

## 1. 必須の権限付与（SQL Editor で実行）

```sql
-- ① カタログを使い、自分のスキーマを作れるようにする（00_setup / 01 / 02 / 04 で必要）
GRANT USE CATALOG, CREATE SCHEMA ON CATALOG <catalog> TO `<group>`;

-- ② Delta Sharing の共有と受信者を作れるようにする（06_delta_sharing で必要）
--    ※ メタストアレベルの権限。既定では付いていません
GRANT CREATE SHARE     ON METASTORE TO `<group>`;
GRANT CREATE RECIPIENT ON METASTORE TO `<group>`;

-- ③ 監査ログを読めるようにする（07_audit_logs で必要）
--    ※ 既定ではアカウント管理者・メタストア管理者のみ
GRANT USE SCHEMA ON SCHEMA system.access TO `<group>`;
GRANT SELECT     ON SCHEMA system.access TO `<group>`;
```

> 💡 `03` の RBAC 演習で参加者が実行する `GRANT` / `REVOKE` も、この同じグループを対象にします
> （`notebooks/core/_config.py` の `PARTICIPANT_GROUP`）。付与先が自分のスキーマ配下なので、
> 参加者は owner として実行できます。

### ③ の注意（重要）

`system.access` への `SELECT` を付与すると、参加者は**自分の操作だけでなく、そのアカウント・
リージョンの監査ログ全体**を読めるようになります。ノートブックでは
`user_identity.email = current_user()` で自分の分に絞っていますが、権限としては全体が見えます。

本番ワークスペースで実施する場合は、この付与が組織のポリシーに反しないか確認してください。
避けたい場合は **07 をスキップし、講師が画面共有で説明する**のが安全です。

### `system` スキーマが有効化されていない場合

`system.access.audit` が存在しない場合、**アカウント管理者による有効化**が必要です
（Catalog → `system` → `access` スキーマの **Enable**、または Account Console の設定）。
有効化しても**ログの反映には数分〜十数分**かかります。

---

## 2. 管理タグ（Governed Tag）の権限 — ⚠️ 最も注意が必要

管理タグは**管理者が事前に作成**し、参加者は `03_access_control` で**付与（ASSIGN）だけ**行います。
関係する権限は 3 種類で、**既定の保有者がそれぞれ違う**点に注意してください。

| 権限 | 何のために | 既定で持つ人 |
|---|---|---|
| **CREATE** | `CREATE GOVERNED TAG` でタグを作る | アカウント管理者・**ワークスペース管理者** |
| **MANAGE** | タグの編集・削除・権限付与 | アカウント管理者／**自分が作ったタグには作成者も自動で付く** |
| **ASSIGN** | タグをテーブル・列に**付与する** | **アカウント管理者のみ**（← 参加者に付与が必要） |

つまり **参加者に必要なのは `ASSIGN`** です。作成は管理者が行うため `CREATE` は不要です。

### 対応方法（どちらか選ぶ）

**方法A: 管理者が事前に管理タグを作成する（推奨）**

管理タグは**アカウント全体で 1 つの定義を共有**するリソースです。
個人ごとに作るものではないため、**管理者が事前に 3 種を作成し、参加者には `ASSIGN` を付与**します。
参加者が `03` を実行すると「既に存在します」と表示され、そのまま進みます
（notebook はこの状態を正常として扱います）。

作成する管理タグ（SQL Editor で実行）:

```sql
CREATE GOVERNED TAG uc_handson_sensitivity
  DESCRIPTION 'Hands-on: column sensitivity level (drives column masking)'
  VALUES ('confidential','internal','public');

CREATE GOVERNED TAG uc_handson_domain
  DESCRIPTION 'Hands-on: business domain of the asset (also drives row filtering)'
  VALUES ('procurement','sales');

CREATE GOVERNED TAG uc_handson_layer
  DESCRIPTION 'Hands-on: data layer'
  VALUES ('master','transaction','analytics');
```

> `CREATE GOVERNED TAG` は `IF NOT EXISTS` 非対応です。既に存在する場合はエラーになりますが、
> その場合はそのまま使えるので無視してください。

一覧:

| タグキー | 許可値 | 使う場所 |
|---|---|---|
| `uc_handson_sensitivity` | `confidential` / `internal` / `public` | 03（列マスクの対象） |
| `uc_handson_domain` | `procurement` / `sales` | 03（行フィルタの判定列＋分類） |
| `uc_handson_layer` | `master` / `transaction` / `analytics` | 03（分類）／05（探索） |

ASSIGN 権限の付与（SQL）:

```sql
-- ⚠️ 管理タグはアカウントレベルのリソースです。
--    `account users` やワークスペースローカルの users / admins は principal として使えません。
--    Account Console で作成し、ワークスペースに追加したグループを指定します。
GRANT ASSIGN ON GOVERNED TAG uc_handson_sensitivity TO `<group>`;
GRANT ASSIGN ON GOVERNED TAG uc_handson_domain      TO `<group>`;
GRANT ASSIGN ON GOVERNED TAG uc_handson_layer       TO `<group>`;

-- 付与状況の確認
SHOW GRANTS ON GOVERNED TAG uc_handson_sensitivity;
```

> 💡 §1 のカタログ / メタストア / `system.access` の付与も、同じグループを指定できます。
> **すべてグループ単位に揃えると、片付けはグループ削除だけで済みます。**

ASSIGN 権限の付与（Catalog Explorer から。まとめて付与したい場合はこちらが楽）:

1. **Catalog** → 上部 **Govern**（盾アイコン）→ **Governed Tags**
2. アカウント全体に付与する場合: **Account Permissions** → **Grant permissions**
   個別タグだけの場合: 対象タグ → **Permissions** → **Grant permissions**
3. **参加者グループ**を選び、**ASSIGN** をチェックして保存

> 付与にはアカウントレベルまたはタグ個別の **MANAGE** 権限が必要です。反映に 30 秒以上かかります。

**方法B: 参加者をワークスペース管理者にする**

検証用の sandbox なら、参加者を `admins` グループに入れる方法もあります
（`CREATE` が既定で付き、自分が作ったタグには `MANAGE` も付きます）。
ただし `ASSIGN` は既定に含まれないため、**方法A（管理者が作成 + ASSIGN 付与）が確実**です。
本番ワークスペースでは管理者権限の付与は避けてください。

---

## 3. 各ノートブックが必要とする権限（対応表）

| notebook | 主な操作 | 必要な権限 |
|---|---|---|
| `00_setup` | スキーマ・Volume 作成、COMMENT | `USE CATALOG` + `CREATE SCHEMA`（自分が作ったスキーマの owner になる） |
| `01_ingest_data` | `samples.tpch` から CTAS | 上記 + `samples` は権限不要 |
| `02_catalog_schema` | COMMENT / PK・FK | 上記のみ |
| `03_access_control` | 参加者グループへの GRANT / **タグ付与** / **ABAC ポリシー** | 上記 + **管理タグの ASSIGN**（§2。CREATE は管理者が実施済みなので不要）+ スキーマ owner（自分のスキーマなので満たす） |
| `04_lineage` | テーブル・ビュー作成 | スキーマ owner（満たす） |
| `05_discovery` | 検索・タグ確認・Certify | スキーマ owner（満たす） |
| `06_delta_sharing` | **Share / Recipient 作成** | **`CREATE SHARE` + `CREATE RECIPIENT` ON METASTORE**（§1-②） |
| `07_audit_logs` | `system.access.audit` の SELECT | **`system.access` の USE SCHEMA + SELECT**（§1-③） |
| `08_genie` | Genie スペース作成 | SQL Warehouse への `CAN_USE`、対象テーブルへの `SELECT`（満たす） |

> 💡 参加者は自分でスキーマを作るため、**そのスキーマとテーブルの owner** になります。
> owner は配下のオブジェクトに対する権限を持つので、`03`〜`05` の操作は追加付与なしで通ります。

---

## 4. 事前確認チェックリスト（前日までに）

管理者と講師で分担して確認してください。

- [ ] 参加者 全員がワークスペースにログインできる
- [ ] **参加者グループを Account Console で作成**し、**参加者を Members に追加**した
- [ ] **そのグループをこのワークスペースに追加**した（Settings → Identity and access → Groups）
- [ ] `GRANT USE CATALOG, CREATE SCHEMA ON CATALOG <catalog> TO \`<group>\`` 実行済み
- [ ] `GRANT CREATE SHARE / CREATE RECIPIENT ON METASTORE TO \`<group>\`` 実行済み
- [ ] `system.access` の `USE SCHEMA` + `SELECT` をグループに付与済み（または 07 をデモに切替と決定）
- [ ] **管理タグ 3 種を管理者が作成済み**、かつグループに **ASSIGN** 付与済み
- [ ] `_config.py` の `DEFAULT_CATALOG` が対象カタログ名になっている
- [ ] **`_config.py` の `PARTICIPANT_GROUP` が作成したグループ名と一致している**
- [ ] SQL Warehouse が起動する（参加者数に対してサイズが十分か）
- [ ] **管理者が、参加者と同じ権限のテストアカウントで `00`〜`08` を通し実行できた**

最後の項目が最も確実な検証です。**管理者アカウントでの成功は、参加者での成功を意味しません**
（管理タグ・Share・監査ログはいずれも管理者だけが既定で持つ権限に依存します）。

---

## 5. 参加者数に応じた注意

- **SQL Warehouse のサイズ**: 6 名程度なら Small で足りますが、同時に Genie を使うと待ちが出ます。
  余裕を見るなら Medium、またはオートスケールの上限を上げてください。
- **管理タグはアカウント共有**: 最初の 1 人が作成し、以降は「既に存在します」と表示されます（正常）。
- **スキーマは自動で分離**: `_config` がログインユーザー名から生成するため衝突しません
  （例 `uc_handson_taro_yamada`）。
