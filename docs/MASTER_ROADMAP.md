# Master Project Roadmap
## Intelligent Investment Recommendation Platform
**Aligned with MarketPulse Industry Standard**
**Updated:** June 2026

---

## Project Status

| Phase | Name | Status |
|-------|------|--------|
| Phase 1  | Research & System Design              | ✅ Complete |
| Phase 2  | Data Platform Foundation              | ✅ Complete |
| Phase 3  | Batch Ingestion — Bronze Layer        | ✅ Complete |
| Phase 4  | Real-Time Streaming — Kinesis         | ✅ Complete |
| Phase 5  | Silver Layer + Great Expectations     | ✅ Complete |
| Phase 6  | Gold Layer — Feature Engineering      | 🔄 In Progress |
| Phase 7  | dbt Transformations                   | ⬜ Pending |
| Phase 8  | Apache Airflow Orchestration          | ⬜ Pending |
| Phase 9  | ML Experimentation + Feature Store    | ⬜ Pending |
| Phase 10 | Backtesting Framework                 | ⬜ Pending |
| Phase 11 | Recommendation Engine                 | ⬜ Pending |
| Phase 12 | Redshift + Power BI Dashboards        | ⬜ Pending |
| Phase 13 | Terraform + GitHub Actions CI/CD      | ⬜ Pending |
| Phase 14 | Monitoring & Observability            | ⬜ Pending |
| Phase 15 | Documentation & Final Presentation    | ⬜ Pending |

---

## Phase-by-Phase Detail

---

### ✅ Phase 1 — Research & System Design
**Goal:** Understand the business problem and make all architectural decisions before writing code.

**Deliverables:**
- Business Document (prediction target, scope, stakeholders)
- Data Source Document (5 sources, API mechanics, rate limits)
- Architecture Diagrams (Batch + Streaming pipelines)
- Success Metrics Document (5 metric categories)

---

### ✅ Phase 2 — Data Platform Foundation
**Goal:** Provision all cloud infrastructure and verify end-to-end connectivity.

**Deliverables:**
- AWS S3 bucket (`investment-platform-husnain`) with 6 folders
- IAM User (`investment-platform-user`) + IAM Role (`DatabricksS3AccessRole`)
- Kinesis Stream (`investment-platform-market-stream`, 2 shards)
- CloudWatch billing alarm
- Databricks Free Edition workspace + 5-folder notebook structure
- Local project repository with `config.yaml`, `.env`, `requirements.txt`
- Verified local → S3 connectivity via `verify_local_s3.py`

---

### 🔄 Phase 3 — Batch Ingestion Pipeline (Bronze Layer)
**Goal:** Ingest raw historical data from all sources into S3 Bronze layer as Delta tables.

**Scripts to build:**
- `src/ingestion/ingest_stocks.py` — Alpaca IEX, 50 equities, 5yr daily bars ✅
- `src/ingestion/ingest_crypto.py` — Alpaca Crypto, 10 assets, 5yr daily bars 🔄
- `src/ingestion/ingest_macro.py` — FRED API, 10 macroeconomic series
- `src/ingestion/ingest_news.py` — News API, financial headlines

**S3 Output:**
```
bronze/
├── stocks/     ← Delta table (62,593 rows) ✅
├── crypto/     ← Delta table (in progress)
├── macro/      ← Delta table
└── news/       ← Delta table
```

---

### ⬜ Phase 4 — Real-Time Streaming (Kinesis)
**Goal:** Stream live market data from Alpaca WebSocket into S3 via Kinesis.

**Components:**
- Alpaca WebSocket producer (`src/streaming/kinesis_producer.py`)
- Kinesis consumer in Databricks (`notebooks/04_streaming/stream_consumer.py`)
- Delta table: `streaming/live_market_stream`

---

### ⬜ Phase 5 — Silver Layer + Great Expectations
**Goal:** Clean, validate, and standardize Bronze data. Catch bad data before it corrupts models.

**Processing:**
- Deduplicate records
- Handle null values and outliers
- Standardize timestamps and schemas
- Join stocks with sector/industry reference data

**Great Expectations (NEW — MarketPulse alignment):**
- Suite 1: Stock price > 0, volume > 0, no nulls in OHLCV
- Suite 2: Crypto price > 0, market cap consistent
- Suite 3: Macro indicators within historical ranges
- Suite 4: News articles have valid dates and non-empty headlines
- 10+ quality checks with automated alerts

**S3 Output:**
```
silver/
├── stocks/    ← Cleaned equities
├── crypto/    ← Cleaned crypto
├── macro/     ← Cleaned macro series
└── news/      ← Cleaned headlines
```

---

### ⬜ Phase 6 — Gold Layer (Feature Engineering)
**Goal:** Compute ML-ready features from Silver data.

**Features to compute:**
- Technical: RSI, MACD, Bollinger Bands, Moving Averages (20d, 50d, 200d)
- Momentum: Price returns (1d, 5d, 20d), volatility
- Macro: VIX regime, yield curve slope, CPI trend
- Sentiment: FinBERT news sentiment scores
- Target variable: 5-day forward return (T+5)

**S3 Output:**
```
gold/
└── features/  ← ML-ready feature table
```

---

### ⬜ Phase 7 — dbt Transformations (NEW — MarketPulse alignment)
**Goal:** Build SQL-based analytical models with tests, documentation, and lineage.

**dbt models to build (15+ models):**
- Staging models: cast and clean Bronze → Silver
- Intermediate models: join tables, compute rolling windows
- Mart models: RSI, MACD, Bollinger Bands, sector aggregations

**dbt tests (30+):**
- `not_null` on all key columns
- `unique` on primary keys
- `accepted_values` on categorical fields
- Custom macros for price sanity checks

**Output:**
- dbt documentation site
- Data lineage graph
- CI-tested SQL transformations

---

### ⬜ Phase 8 — Apache Airflow Orchestration (NEW — MarketPulse alignment)
**Goal:** Schedule and automate all pipeline stages. No more manual script execution.

**5 Airflow DAGs:**
- `DAG 1 — Ingest`: Pull APIs → write to Bronze (runs daily at 6 AM)
- `DAG 2 — Process`: Bronze → Silver → Gold transformation
- `DAG 3 — Transform`: dbt run + dbt test
- `DAG 4 — Quality`: Great Expectations validation, alert on failure
- `DAG 5 — ML`: Nightly model retraining + evaluation

**Setup:** Apache Airflow running locally (Docker) or AWS MWAA

---

### ⬜ Phase 9 — ML Experimentation + Feature Store
**Goal:** Train multiple models, track experiments, and register the best model.

**Models to train:**
- Baseline: Linear Regression
- Tree: Random Forest, XGBoost, LightGBM
- Deep Learning: LSTM

**MLflow tracking (per experiment):**
- Metrics: IC, ICIR, Directional Accuracy, RMSE, Sharpe Ratio
- Parameters: hyperparameters, feature sets, date ranges
- Artifacts: trained model, confusion matrix, feature importance

**Databricks Feature Store (NEW — MarketPulse alignment):**
- Register Gold features in Feature Store
- Enable point-in-time correct feature lookups
- Prevent data leakage

---

### ⬜ Phase 10 — Backtesting Framework
**Goal:** Simulate historical trading using model predictions.

**Metrics:**
- Sharpe Ratio, Sortino Ratio, Max Drawdown, CAGR
- Win Rate vs S&P 500 benchmark
- Top-5 Hit Rate, Bottom-5 Hit Rate

---

### ⬜ Phase 11 — Recommendation Engine
**Goal:** Convert model predictions into ranked investment recommendations.

**Output:**
- Top 5 opportunities
- Bottom 5 opportunities
- Confidence scores and risk scores
- Explainability (SHAP values)

---

### ⬜ Phase 12 — Redshift + Power BI Dashboards (EXTENDED — MarketPulse alignment)
**Goal:** Serve analytics to business users via dashboards.

**Amazon Redshift (NEW):**
- Load Gold tables from S3 into Redshift
- Enable fast SQL analytics on the full dataset

**Power BI Dashboards (5):**
- Executive Dashboard: Top/Bottom 5 recommendations
- Market Dashboard: Price trends, technical signals
- Streaming Dashboard: Live Kinesis feed
- ML Dashboard: Model performance over time
- Portfolio Dashboard: Backtesting results

---

### ⬜ Phase 13 — Terraform + GitHub Actions CI/CD (NEW — MarketPulse alignment)
**Goal:** Codify all infrastructure and automate deployment.

**Terraform:**
- S3 bucket, Kinesis stream, IAM roles
- Redshift cluster
- CloudWatch alarms

**GitHub Actions:**
- On every `git push`: run dbt tests automatically
- On `main` branch merge: deploy dbt models + trigger Airflow DAG

---

### ⬜ Phase 14 — Monitoring & Observability
**Goal:** Production-grade alerting and pipeline health monitoring.

**CloudWatch dashboards:**
- Kinesis stream lag metrics
- Pipeline success/failure rates
- ML model performance drift alerts

---

### ⬜ Phase 15 — Documentation & Final Presentation
**Goal:** Document everything. Present end-to-end system.

**Deliverables:**
- README with architecture overview
- Setup and deployment guide
- dbt documentation (generated)
- API documentation for model serving endpoint
- Final slide deck: architecture, decisions, cost analysis, lessons learned

---

## Technology Stack Summary

| Category | Technology |
|----------|-----------|
| Cloud | AWS (S3, Kinesis, IAM, CloudWatch, Redshift) |
| Compute | Databricks Free Edition (Serverless) |
| Languages | Python, SQL |
| Data Format | Delta Lake |
| Ingestion | Alpaca, FRED, News API |
| Transformation | dbt |
| Orchestration | Apache Airflow |
| Data Quality | Great Expectations |
| ML Tracking | MLflow |
| Feature Store | Databricks Feature Store |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| BI | Power BI |
| Version Control | Git + GitHub |
