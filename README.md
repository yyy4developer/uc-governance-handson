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

1. メタデータ設計（COMMENT / タグ / 主キー・外部キー、**AI 生成コメント**）
2. アクセス制御 — 階層的 GRANT、管理タグ、**Tag Policies（許可値の統制）**、
   **ABAC**（タグ駆動の行フィルタ・列マスクポリシー）
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
**同じ GRANT / リネージ / Genie がそのまま効く**ことを示すものです。

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
- Serverless SQL Warehouse（`%sql` セル / Genie 用）
- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/index.html)（`databricks bundle` を使用）
- **あり版のみ**: AWS アカウント + [Terraform](https://developer.hashicorp.com/terraform/downloads)

---

## セットアップ

### 1. 認証

```bash
databricks auth login --host https://<your-workspace>.cloud.databricks.com
```

### 2. カタログ名を設定する（講師側、1 箇所だけ）

`notebooks/core/_config.py` の `DEFAULT_CATALOG` を、使用するワークスペースの
既存カタログ名に書き換えます。**参加者が編集する必要はありません**。

```python
DEFAULT_CATALOG = "<your_catalog>"
```

スキーマは `_config` が**ログインユーザー名から自動生成**します（例 `uc_handson_taro_yamada`）。
これにより複数人が同じワークスペースで同時に作業しても衝突しません。

参加者に必要なカタログ権限（管理者が事前に付与）:

```sql
GRANT USE CATALOG, CREATE SCHEMA ON CATALOG <your_catalog> TO `account users`;
```

> ⚠️ Unity Catalog の principal は `account users` です。ワークスペースローカルの
> `users` グループを指定すると `PRINCIPAL_DOES_NOT_EXIST` になります。

### 3. ハンズオンの進め方（参加者）

参加者は **Git folder としてこのリポジトリを取り込み**、`notebooks/core/` の
`00_setup` から `08_genie` までを順に実行します。詳細は [HANDSON.md](./HANDSON.md)。

### （任意）講師が事前に動作確認する場合

```bash
databricks bundle validate -t dev

databricks bundle deploy -t dev \
  --var catalog=<your_catalog> \
  --var warehouse_id=<your_warehouse_id> \
  --auto-approve

# 初期化ジョブ（実行した人のスキーマに対して 00→01→02 を実行）
databricks bundle run uc-handson-core-init -t dev \
  --var catalog=<your_catalog> --var warehouse_id=<your_warehouse_id>
```

> このジョブは `schema` を渡しません（`_config` のユーザー別自動判定に任せるため）。
> ハンズオン本番では参加者が UI から 00→01→02 を順に実行するのが基本です。

#### アクセス制御デモ（03）は ABAC ポリシーベース

`03_access_control` は **属性ベースアクセス制御（ABAC）** で構成しています。
**管理タグ（Governed Tag）を列に付け、タグ条件でポリシーを1本張る**と、スキーマ配下の
該当タグを持つ列すべてに行フィルタ/列マスクが自動適用されます（`SET ROW FILTER`/`SET MASK`
をテーブルごとに付ける従来方式との違いがデモの見どころ）。

- **グループが無くても実演可能**: ポリシー適用中は `is_account_group_member(...)` が
  false のユーザー（多くの sandbox の実行者）が「マスク/フィルタされる側」になり、
  ABAC が効いている様子をそのまま観察できます。
- 「管理者は全件・実値、営業は担当セグメントのみ」という**両側**を見せたい場合のみ、
  以下のグループを作成し、片方のユーザーを管理者グループに入れて別ユーザーで確認します。

```bash
# グループ作成（例。両側を実演する場合のみ）
for g in data_governance_admins sales_automobile sales_building sales_machinery; do
  databricks groups create --display-name "$g"
done
#   Account Console / SCIM で <your-user-id> を data_governance_admins に追加
```

- 使用する管理タグ（デモ専用キー。アカウント内で衝突しないよう prefix 付き）:
  `uc_handson_pii`（列マスク対象）/ `uc_handson_segment`（行フィルタ判定列）
- ⚠️ **03 の末尾で必ずポリシーとタグを解除**します（付けたまま 04 に進むと `customer` が
  0 行/NULL に見え、04 の JOIN 結果が空になるため）。ノートブックの「8. 後片付け」セルが自動実行します。
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

# terraform output で得た catalog 名を bundle 変数に渡す
databricks bundle run uc-handson-federation-demo -t dev \
  --var fed_catalog_glue=$(terraform output -raw ...) \
  --var fed_catalog_redshift=$(terraform output -raw ...)
```

詳細は `terraform/terraform.tfvars.example` と `notebooks/federation/00_prereq_env.py` を参照。

---

## クリーンアップ

```bash
# bundle（notebook / job を削除）
databricks bundle destroy -t dev

# 参加者が作ったスキーマを消す場合（SQL）
#   DROP SCHEMA IF EXISTS <catalog>.uc_handson_<user> CASCADE;

# 参考実装の Federation を試した場合のみ
cd terraform && terraform destroy
```

---

## ディレクトリ構成

```
uc-governance-handson/
├── HANDSON.md                # ⭐ 参加者向けの進行ガイド
├── databricks.yml            # DAB 定義
├── resources/                # DAB リソース（jobs）
├── notebooks/core/           # ⭐ ハンズオン本体（_config, 00_setup 〜 08_genie）
├── notebooks/federation/     # 参考実装（ハンズオン対象外）
├── terraform/                # 参考実装の環境構築（ハンズオン対象外）
└── docs/architecture.md      # アーキテクチャ図
```

---

## 注意

- このリポジトリは**特定顧客の情報を一切含まず**、いつでも public 化できる設計です。
- 平文の secret（PAT / password / token）はコミットしません。`terraform.tfvars`（gitignore 済み）/
  環境変数 / `dbutils.secrets` を使用します。
- 生成データはすべて合成データです。
