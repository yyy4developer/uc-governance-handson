# Unity Catalog ガバナンス ハンズオン

Databricks **Unity Catalog** のデータガバナンス機能と **Lakehouse Federation** を、
手を動かしながら学ぶハンズオン用デモです。製造業（設備保全・品質管理）の汎用シナリオを題材にしています。

デモは 2 構成に分かれています。

| 構成 | ディレクトリ | 内容 | 前提リソース |
|---|---|---|---|
| **なし版**（UC ガバナンス単体） | `notebooks/core/` | カタログ作成 → アクセス制御（**ABAC**） → リネージ → データ探索 → Delta Sharing → 監査ログ → Genie | Databricks workspace のみ（`samples.tpch` を利用） |
| **あり版**（Lakehouse Federation） | `notebooks/federation/` | AWS Glue（Catalog Federation）+ Amazon Redshift（Query Federation）を UC 傘下で統合 | AWS（`terraform/` で構築） |

> **ストーリー**: なし版で「UC の中に閉じた世界」でガバナンスを体験 → あり版で「現実には Glue / Redshift にデータが散在」→ Federation で移動なしに UC 傘下に取り込み、**同じ GRANT / リネージ / Genie がそのまま効く**（ガバナンスの一貫性）ことを見せます。

すべての実行と UI 操作手順は各 notebook 内（`%sql` セル / `%md` セル）に含まれています。

---

## シナリオ

構築を簡易にするため、**なし版**と**あり版**でソースを分けています（各版は単体で完結）。

### なし版 — 部品調達・受注（`samples.tpch`）

Databricks 標準サンプル `samples.tpch` を自スキーマに取り込んで利用（合成データ生成は不要）。

| 論理領域 | テーブル |
|---|---|
| マスタ | `region` / `nation` / `supplier` / `part` / `customer` |
| トランザクション | `orders` / `lineitem`（受注 5,000 件のサブセット） |
| 分析結果 | `order_analysis_summary`（JOIN で作成） |

ペルソナ: `data_governance_admins` / `procurement_team` / `sales_analysts` / `executives`

### あり版 — 製造業（設備保全・工場データ、`terraform/` で構築）

架空の精密機器メーカー。`machine_id` を共通キーに、Glue（マスタ）と Redshift（トランザクション）に散在。

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

### 2. なし版（Terraform 不要）

```bash
# バリデーション
databricks bundle validate -t dev

# デプロイ（notebook / job を配置）
databricks bundle deploy -t dev \
  --var catalog=<your_catalog> \
  --var schema=uc_handson \
  --var warehouse_id=<your_warehouse_id> \
  --auto-approve

# 初期化ジョブ（schema/volume 作成 → samples.tpch 取り込み → カタログ整備）を実行
databricks bundle run uc-handson-core-init -t dev \
  --var catalog=<your_catalog> --var schema=uc_handson --var warehouse_id=<your_warehouse_id>
```

以降、`notebooks/core/03_access_control.py` 〜 `08_genie.py` を Databricks UI 上で
1 つずつインタラクティブに実行します（`HANDSON.md` の進行に沿って）。

> **03〜08 の catalog/schema 設定**: 各ノートブックは冒頭で `%run ./_config` を実行します。
> 環境が違う場合は **`notebooks/core/_config.py` の `DEFAULT_CATALOG` / `DEFAULT_SCHEMA` の 2 行だけ**
> 書き換えれば、03〜08 はそのまま Run できます（schema / volume は `00_setup.py` が作成）。

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
  0 行/NULL に見え、04 の JOIN 結果が空になるため）。ノートブックの「7. 後片付け」セルが自動実行します。
- ⚠️ グループメンバーシップやタグが SQL エンジンに反映されるまで**数分**かかることがあります。
- ABAC には **Governed Tag が必須**（通常タグ不可）。`CREATE GOVERNED TAG` は `IF NOT EXISTS` 非対応。

### 3. あり版（AWS Federation）

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
# あり版の AWS リソース
cd terraform && terraform destroy

# bundle
databricks bundle destroy -t dev
```

---

## ディレクトリ構成

```
uc-governance-handson/
├── databricks.yml            # DAB 定義
├── resources/                # DAB リソース（schema/volume, jobs）
├── notebooks/core/           # なし版（00_setup 〜 08_genie）
├── notebooks/federation/     # あり版（00_prereq_env 〜 05_genie_federation）
├── terraform/                # あり版の環境構築（Glue + Redshift のみ）
├── scripts/                  # 合成データ生成の共通ロジック
└── docs/architecture.md      # アーキテクチャ図
```

---

## 注意

- このリポジトリは**特定顧客の情報を一切含まず**、いつでも public 化できる設計です。
- 平文の secret（PAT / password / token）はコミットしません。`terraform.tfvars`（gitignore 済み）/
  環境変数 / `dbutils.secrets` を使用します。
- 生成データはすべて合成データです。
