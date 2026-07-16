# MarketPulse — Data Engineering Project (Azure + Databricks)
**Author:** Intern B (Azure + Databricks Hybrid Stack)  
**Project Scope:** Ingest, process, transform, and analyze real-time financial market data, train machine learning models, and orchestrate the pipeline at scale.

---

## 1. System Architecture

MarketPulse utilizes a modern medallion lakehouse architecture deployed on Azure:

* **Ingestion (Bronze):** Batch historical data ingestion using `yfinance` and streaming ticks using `Alpaca WebSockets` into **Azure Data Lake Storage (ADLS) Gen2** via **Azure Event Hubs**.
* **Processing (Silver):** PySpark processing on Databricks to clean, deduplicate, validate schemas, and run news sentiment inference using FinBERT.
* **Analytics Feature Store (Gold):** Aggregated metrics, technical indicators (RSI, MACD, Bollinger Bands), and macro indicators loaded to Delta tables.
* **Machine Learning (MLflow):** Ridge regression model trained on gold features to predict next-day Sharpe ratios and price movements, registered in the local MLflow Model Registry.
* **Orchestration (Airflow):** Chained execution workflow running nightly in an Airflow container host.
* **Data Warehouse (Serving):** Loader ETL streams Gold Delta tables to **Azure Synapse Dedicated SQL Pool** (with local SQLite fallback to `analytics.db`).

---

## 2. Deliverables & Directory Structure

* `src/ingestion/` — Batch and streaming ingest scripts (yfinance, Event Hubs producers).
* `src/processing/` — Spark cleaning and FinBERT sentiment inference jobs.
* `src/ml/` — Model training script logging leaderboard metrics to `mlruns.db`.
* `src/backtesting/` — Strategy backtester generating comparison curve charts (`docs/backtest_equity_curve.png`).
* `src/recommendation/` — Volatility risk and model explainability engine (`docs/latest_recommendations.md`).
* `src/analytics/` — Database loader script (`azure_sql_loader.py`) and Synapse DDL definitions (`schema.sql`).
* `dbt_project/` — DBT semantic models, macros, schema validations, and profiles.
* `airflow/dags/` — Nightly ML DAG automation script (`ml_dag.py`) and helper operators.
* `terraform/` — IaC configurations to provision all Azure services.
* `docs/csv/` — Materialized CSV data tables for instant Power BI import.
* `docs/presentation_deck.md` — Slide deck summary with comparative cost analysis and architecture diagrams.

---

## 3. How to Run the Local Sandbox Demo (Offline Plan)

Since the Azure student subscription has ended, the platform uses its fully operational local sandbox mode for demonstration:

### 1. Power BI Visualization
All data warehouse tables have been exported to CSVs:
* `docs/csv/gold_features.csv` (75,079 rows)
* `docs/csv/backtest_report.csv` (266 rows)
* `docs/csv/recommendations.csv` (10 signals)

To demo, open Power BI Desktop, select **Get Data -> Text/CSV**, load these files, and map your visual dashboard directly.

### 2. MLflow Experiments UI
To launch the local MLflow dashboard and showcase the leaderboard:
```bash
# Start MLflow server using local sqlite backend
mlflow ui --backend-store-uri sqlite:///mlruns.db
```
Open **`http://localhost:5000`** to review model configurations, metrics, validation parameters, and the registered model registry.

### 3. Strategy Backtest Results
Showcase the temporal strategy vs. benchmark performance curve located at: `docs/backtest_equity_curve.png`.

---

## 4. Production Cloud Deployment Guide

When a new Azure subscription is provisioned, you can deploy the entire infrastructure to the cloud:

### 1. Infrastructure Provisioning (Terraform)
```bash
# Navigate to terraform folder
cd terraform

# Initialize and pull providers
terraform init

# Validate configuration syntax
terraform validate

# Deploy resources to Azure (provide variables)
terraform apply -var="synapse_admin_password=YourPassword123" -var="ssh_public_key=ssh-rsa ..."
```

### 2. Pipeline Execution
Update the `.env` file with the newly generated outputs from Terraform (Synapse endpoints, storage keys, and event hub connection strings).

Build and run the loader container:
```bash
# Rebuild the processing image
docker compose build

# Stream data to Azure Synapse SQL Pool
docker compose run --rm processing src/analytics/azure_sql_loader.py
```
This script will automatically authenticate via SSL using `python-tds` and load the Gold features to your Azure Synapse Dedicated SQL Pool.
