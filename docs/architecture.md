# アーキテクチャ

## ハンズオン本体（`notebooks/core/`）— UC ガバナンス単体

すべて Databricks native（Delta）。追加のクラウドリソースなしで UC のガバナンス機能を学びます。
題材は Databricks 標準サンプル **`samples.tpch`**（部品調達・受注）。

```
┌──────────────────────────────────────────────────────────────────┐
│                       Unity Catalog                              │
│  <catalog>.uc_handson_<参加者>   ← 参加者ごとに自動で分離           │
│                                                                  │
│   マスタ              トランザクション        分析                  │
│  ┌───────────┐       ┌──────────────┐     ┌────────────────────┐ │
│  │ region    │       │ orders       │     │ order_analysis_    │ │
│  │ nation    │──────▶│  (5,000件)   │────▶│   summary          │ │
│  │ customer  │       │ lineitem     │     │  (JOIN 生成)        │ │
│  │ part      │       │  (約2万件)   │     └─────────┬──────────┘ │
│  │ supplier  │       └──────────────┘               │            │
│  └───────────┘                                      ▼            │
│                                        ┌────────────────────────┐│
│                                        │ segment_revenue_view   ││
│                                        └────────────────────────┘│
│                                                                  │
│  ガバナンス: RBAC(GRANT) / 管理タグ / ABAC(行フィルタ・列マスク) /  │
│              リネージ / タグ検索 / Delta Sharing / 監査 / Genie    │
└────────────────────────┬─────────────────────────────────────────┘
                         │ 「実体はここ」という参照
                         ▼
            ┌─────────────────────────────────┐
            │  クラウドストレージ（実データ）    │
            │  abfss://... / s3://  Delta 形式 │
            └─────────────────────────────────┘
```

**UC はメタデータの層**であり、実データはクラウドストレージに置かれたままです
（＝仮想的な統合）。この点は `01_ingest_data` で実際に `Storage location` を確認します。

主な結合キー: `c_custkey`（顧客）／`o_orderkey`（受注）／`l_partkey`・`l_suppkey`（部品・供給元）。

### notebook の構成

| | 内容 |
|---|---|
| `notebooks/core/` | **ハンズオン本体**（`00`〜`08` + `99_cleanup`） |
| `notebooks/admin/` | 管理者向け（`00` 事前準備 / `01` 片付け） |
| `notebooks/federation/` + `terraform/` | 参考実装（ハンズオン対象外。下記） |

---

## 参考実装（ハンズオン対象外）— Lakehouse Federation

> ⚠️ **ハンズオンでは実施しません。** AWS 側のリソース構築（Glue / Redshift / IAM /
> ネットワーク）が必要なためです。当日はコンセプトの説明にとどめ、動作は別途デモでご覧いただきます。
> 以下は `notebooks/federation/` と `terraform/` の参考実装の構成です
> （こちらは製造 IoT を題材にした別シナリオです）。

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
