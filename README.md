# Unity Catalog ガバナンス ハンズオン

Databricks **Unity Catalog** のデータガバナンス機能を、手を動かしながら学ぶハンズオン教材です。
Databricks 標準サンプル `samples.tpch`（部品調達・受注データ）を題材に、
**追加のクラウドリソースなし**で一通り体験できます。

## 👉 参加者向けの手順は [HANDSON.md](./HANDSON.md) へ

| | 内容 |
|---|---|
| **対象** | `notebooks/core/`（00〜08） |
| **所要** | 1〜2時間 |
| **前提** | Databricks workspace（Unity Catalog 有効）+ Serverless SQL Warehouse のみ |
| **進め方** | **画面操作（UI）中心**。各ノートブックを実行 → Catalog Explorer で結果を確認 |
| **複数人** | スキーマが**参加者ごとに自動で分かれる**ので、同じワークスペースで同時実施できる |

カバーする機能:

1. メタデータ設計（COMMENT / 主キー・外部キー、**AI 生成コメント**）
2. アクセス制御 — **RBAC**（GRANT / REVOKE と権限の継承）、管理タグと
   **Tag Policies（許可値の統制）**、**ABAC**（タグ駆動の行フィルタ・列マスク）
3. データリネージ（テーブル / 列レベル）
4. データ探索（検索・タグ・Certified・Insights）
5. 組織間データ共有（Delta Sharing D2D / D2O）
6. 監査ログ（`system.access.audit`）
7. AI/BI Genie（自然言語でのデータ活用）

すべての実行手順と UI 操作手順は、各 notebook 内（`%md` セル）に含まれています。

---

## シナリオ — 部品調達・受注（`samples.tpch`）

Databricks 標準サンプル `samples.tpch` を自分のスキーマに取り込んで利用します（データ生成は不要）。

| 論理領域 | テーブル |
|---|---|
| マスタ | `region` / `nation` / `supplier` / `part` / `customer` |
| トランザクション | `orders` / `lineitem`（受注 5,000 件のサブセット） |
| 分析結果 | `order_analysis_summary`（JOIN で作成） |

アクセス制御で使うペルソナ（グループ）: `data_governance_admins` / `sales_automobile` /
`sales_building` / `sales_machinery`

> グループが未作成でも進められます。その場合、実行者は「マスク・フィルタが**効く側**」として
> ABAC の動作を観察できます（詳細は `03_access_control` 内の説明を参照）。

---

## 📎 参考実装（ハンズオン対象外）— Lakehouse Federation

`notebooks/federation/` と `terraform/` には、**Lakehouse Federation** の実装例が入っています。
AWS Glue（Catalog Federation）と Amazon Redshift（Query Federation）を Unity Catalog 傘下に取り込み、
**同じ枠組みで GRANT / リネージ / 監査 / Genie を効かせられる**ことを示すものです
（機能ごとに制約はあるため、個別の可否は要件に応じて確認してください）。

> ⚠️ **ハンズオンでは実施しません**。AWS 側のリソース構築（Glue / Redshift / IAM / ネットワーク）が
> 必要で、環境準備に時間とコストがかかるためです。
> ハンズオンでは Federation は**コンセプトの説明**にとどめ、動作は別途デモでご覧いただく想定です。
>
> 自分の AWS 環境で試したい場合の手順は下記「参考: Federation 環境の構築」を参照してください
> （動作検証済みですが、`terraform apply` は実際の AWS 課金が発生します）。

| 論理領域 | テーブル | 置き場所 |
|---|---|---|
| マスタ | `machines` / `sensors` / `quality_inspections` | **AWS Glue**（Catalog Federation） |
| トランザクション | `sensor_readings` / `production_events` | **Amazon Redshift**（Query Federation） |
| 分析結果 | `machine_health_summary` | union catalog（Glue × Redshift のクロスソース JOIN） |

---

## 前提条件

- Databricks workspace（Unity Catalog 有効）
- Serverless コンピュート（ノートブック実行用）と Serverless SQL Warehouse（Genie 用）
- **ブラウザだけで完結します** — CLI やローカル環境の準備は不要です

---

## セットアップ（すべて画面操作）

### 1. カタログ名を設定する（講師のみ、1 行だけ）

`notebooks/core/_config.py` を Databricks の画面で開き、`DEFAULT_CATALOG` を
使用するワークスペースの既存カタログ名に書き換えます。

```python
DEFAULT_CATALOG = "<your_catalog>"
```

スキーマは `_config` が**ログインユーザー名から自動生成**します（例 `uc_handson_taro_yamada`）。
そのため**参加者は何も編集する必要がなく**、複数人が同じワークスペースで同時に作業しても衝突しません。

### 2. 参加者に権限を付与する（講師 / 管理者のみ）

ワークスペースの **SQL Editor** を開き、次を実行します。

```sql
-- カタログ利用と自分のスキーマ作成（00〜05 で必要）
GRANT USE CATALOG, CREATE SCHEMA ON CATALOG <your_catalog> TO `account users`;

-- Delta Sharing（06 で必要。既定では付いていません）
GRANT CREATE SHARE     ON METASTORE TO `account users`;
GRANT CREATE RECIPIENT ON METASTORE TO `account users`;

-- 監査ログ（07 で必要。既定では管理者のみ）
GRANT USE SCHEMA ON SCHEMA system.access TO `account users`;
GRANT SELECT     ON SCHEMA system.access TO `account users`;
```

> ⚠️ Unity Catalog の principal は `account users` です。ワークスペースローカルの
> `users` グループを指定すると `PRINCIPAL_DOES_NOT_EXIST` になります。

**さらに管理タグ（Governed Tag）の権限が必要です**（03 で使用）。
既定ではワークスペース管理者しか作成・付与できないため、講師が事前にタグを作り、
参加者に **ASSIGN** 権限を付与するか、参加者を管理者グループに入れます。

📋 **詳細と事前確認チェックリストは [docs/permissions.md](./docs/permissions.md) にまとめています。
実施前に必ず一読してください。**

### 3. ハンズオンの進め方（参加者）

1. このリポジトリを **Git folder** としてワークスペースに取り込む
   （**Workspace → Create → Git folder** に URL を貼るだけ）
2. `notebooks/core/` の `00_setup` から `08_genie` までを、**▶ Run all** で順に実行
3. 各ステップごとに Catalog Explorer で結果を画面確認

詳細な進行は [HANDSON.md](./HANDSON.md) にあります。

> 💡 **ジョブやバンドル（DAB）のデプロイは不要です**。参加者は Git folder 内のノートブックを
> そのまま実行するだけで、スキーマ作成からデータ取り込みまで完了します。
> 講師が事前確認する場合も、同じノートブックを順に実行するだけです。

#### アクセス制御（03）は RBAC → ABAC の二段構成

`03_access_control` は前半で **RBAC**（`GRANT` / `REVOKE` と権限の継承。隣の参加者と
相互付与するペア演習）、後半で **ABAC** を扱います。ABAC では
**管理タグ（Governed Tag）を列に付け、タグ条件でポリシーを1本張る**と、スキーマ配下の
該当タグを持つ列すべてに行フィルタ/列マスクが自動適用されます（`SET ROW FILTER`/`SET MASK`
をテーブルごとに付ける従来方式との違いがデモの見どころ）。

- **グループが無くても実演可能**: ポリシー適用中は `is_account_group_member(...)` が
  false のユーザー（多くの sandbox の実行者）が「マスク/フィルタされる側」になり、
  ABAC が効いている様子をそのまま観察できます。
- 「管理者は全件・実値、営業は担当セグメントのみ」という**両側**を見せたい場合のみ、
  以下のグループを作成し、片方のユーザーを管理者グループに入れて別ユーザーで確認します。

グループは **Account Console → User management → Groups** から作成し、
ワークスペースに割り当てます（`data_governance_admins` / `sales_automobile` /
`sales_building` / `sales_machinery`）。片方のユーザーを管理者グループに入れてください。

- 使用する管理タグ（デモ専用キー。アカウント内で衝突しないよう prefix 付き）:
  `uc_handson_sensitivity`（列マスク対象）/ `uc_handson_domain`（行フィルタ判定列・分類）/ `uc_handson_layer`（分類）
- ⚠️ **03 の末尾で必ずポリシーを解除**します（付けたまま 04 に進むと `customer` が
  0 行/NULL に見え、04 の JOIN 結果が空になるため）。ノートブックの「9. 後片付け」セルが自動実行します。
  タグは `05` の探索で使うので残します。
- ⚠️ グループメンバーシップやタグが SQL エンジンに反映されるまで**数分**かかることがあります。
- ABAC には **Governed Tag が必須**（通常タグ不可）。`CREATE GOVERNED TAG` は `IF NOT EXISTS` 非対応。
- 管理タグは**アカウント全体で共有**されるため、複数人で実施すると 2 人目以降は
  「既に存在します」と表示されます（正常。タグは共有し、ポリシーは各自のスキーマに張られます）。

---

## 参考: Federation 環境の構築（ハンズオン対象外）

⚠️ この節は**ハンズオンでは実施しません**。自分の AWS 環境で試す場合のみ参照してください。
`terraform apply` は実際の AWS 課金が発生します（Glue / Redshift Serverless / S3 / VPC / IAM）。

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars を編集（databricks_host, redshift_admin_password など）
#   ※ terraform.tfvars は .gitignore 済み。secret はここにのみ書く。

terraform init
terraform apply       # Glue / Redshift / IAM / UC connection / foreign catalog を作成
terraform output      # 作成された foreign catalog 名を確認
```

構築後、`notebooks/federation/` のノートブックを Databricks の画面で開き、
冒頭のカタログ名を `terraform output` の値に合わせてから実行します。

詳細は `terraform/terraform.tfvars.example` と `notebooks/federation/00_prereq_env.py` を参照。

---

## クリーンアップ

**`notebooks/core/99_cleanup` を実行**すると、自分が作ったものを一括削除できます
（ポリシー・関数・Delta Share・スキーマごと）。削除対象を先に一覧表示し、
`CONFIRM = True` にしてから実行する二段構えです。

管理タグはアカウント共有のため既定では残します（全参加者の完了後、講師が任意で削除）。
Genie スペースと Git folder は画面から削除してください（notebook 内に手順あり）。

参考実装の Federation を試した場合のみ:

```bash
cd terraform && terraform destroy
```

---

## ディレクトリ構成

```
uc-governance-handson/
├── HANDSON.md                # ⭐ 参加者向けの進行ガイド
├── notebooks/core/           # ⭐ ハンズオン本体（_config, 00_setup 〜 08_genie, 99_cleanup）
├── notebooks/federation/     # 参考実装（ハンズオン対象外）
├── terraform/                # 参考実装の環境構築（ハンズオン対象外）
└── docs/architecture.md      # アーキテクチャ図
```

すべてブラウザ上の操作で完結するため、ビルド設定やデプロイ定義はありません。

---

## 注意

- このリポジトリは**特定顧客の情報を一切含まず**、いつでも public 化できる設計です。
- 平文の secret（PAT / password / token）はコミットしません。`terraform.tfvars`（gitignore 済み）/
  環境変数 / `dbutils.secrets` を使用します。
- 生成データはすべて合成データです。
