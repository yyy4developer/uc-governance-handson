# アーキテクチャ

## なし版（Federation なし）— UC ガバナンス単体

すべて Databricks native（Delta）。UC のガバナンス機能を単体で学ぶ。

```
┌─────────────────────────────────────────────────────────────┐
│                    Unity Catalog                            │
│  <catalog>.<schema>                                         │
│                                                             │
│   マスタ            トランザクション        分析              │
│  ┌──────────┐      ┌────────────────┐    ┌──────────────┐   │
│  │ factories│      │ sensor_readings│    │ machine_     │   │
│  │ machines │─────▶│ production_    │───▶│ health_      │   │
│  │ sensors  │      │   events       │    │ summary      │   │
│  │ prod_lines│     │ quality_       │    │ (JOIN 生成)   │   │
│  └──────────┘      │  inspections   │    └──────────────┘   │
│                    └────────────────┘                       │
│                                                             │
│  ガバナンス: GRANT / 行フィルタ / 列マスク / リネージ /       │
│              タグ検索 / Delta Sharing / 監査ログ / Genie      │
└─────────────────────────────────────────────────────────────┘
```

共通キー: `factory_id`（FAC-01/02/03）、`machine_id`（1..20）。

---

## あり版（Federation あり）— Glue + Redshift を UC 傘下に統合

現実には別々のシステムに散在するデータを、**コピーせず** Unity Catalog で統合ガバナンス。

```
┌───────────────────────────────────────────────────────────────────┐
│                        Unity Catalog                              │
│                                                                   │
│  Catalog Federation          Query Federation                     │
│  ┌────────────────┐          ┌────────────────────┐               │
│  │ ucf_catalog_glue│          │ ucf_query_redshift │               │
│  │ (S3 直接読取)   │          │ (JDBC pushdown)    │               │
│  │  machines       │          │  sensor_readings   │               │
│  │  sensors        │          │  production_events │               │
│  │  quality_insp.  │          │  quality_insp.     │               │
│  └───────┬─────────┘          └─────────┬──────────┘               │
│          │                              │                          │
│          └──────────┬───────────────────┘                          │
│                     ▼  クロスソース JOIN                            │
│           ┌────────────────────────┐                              │
│           │ ucf_union_dbx.analysis │                              │
│           │  machine_health_summary│                              │
│           └────────────────────────┘                              │
│                                                                   │
│  → なし版と同じ GRANT / リネージ / Genie がそのまま適用             │
└───────────┬───────────────────────────────┬───────────────────────┘
            │ metadata API + S3 直接読取     │ JDBC (pushdown)
   ┌────────▼────────┐             ┌─────────▼──────────┐
   │  AWS Glue / S3  │             │ Amazon Redshift    │
   │ (Parquet/Delta/ │             │  Serverless        │
   │  Iceberg)       │             │                    │
   └─────────────────┘             └────────────────────┘
```

### データソースの対比

| ソース | Federation 方式 | 仕組み | データの所在 |
|---|---|---|---|
| **AWS Glue** | Catalog Federation | メタデータ API 経由 → S3 を Databricks が直接読取（Spark） | S3（Parquet/Delta/Iceberg） |
| **Amazon Redshift** | Query Federation | JDBC 経由でクエリを Redshift 側にプッシュダウン、結果のみ返却 | Redshift |

### 環境構築（`terraform/`）

Glue（S3 + IAM + Glue DB/Table + ETL でデータ投入）、Redshift Serverless（VPC + namespace/workgroup + Data API で DDL/DML）、
UC（service/storage credential + external location + connection + foreign catalog）を Terraform で構築。
`random_string.suffix` でマルチユーザー衝突を回避。
