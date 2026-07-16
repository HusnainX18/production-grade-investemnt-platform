# MarketPulse — Data Engineering Project (AWS + Databricks)
**Author:** Intern A (AWS + Databricks Hybrid Stack)  
**Project Scope:** Ingest, process, transform, and analyze real-time financial market data, train machine learning models, and orchestrate the pipeline at scale.

---

## 1. System Architecture

MarketPulse utilizes a modern serverless Medallion Lakehouse architecture deployed on AWS and Databricks:

* **Ingestion (Bronze):** Batch historical data ingestion using `yfinance`/`Alpaca` and streaming ticks using `Alpaca WebSockets` into **AWS S3** via **AWS Kinesis Streams**.
* **Processing (Silver):** PySpark/Pandas processing on Databricks to clean, deduplicate, validate schemas, and run news sentiment inference using FinBERT.
* **Analytics Feature Store (Gold):** Aggregated metrics, technical indicators (RSI, MACD, Bollinger Bands), and macro indicators loaded to Delta tables.
* **Machine Learning (MLflow):** LSTM regressor model trained on gold features to predict next-day Sharpe ratios and price movements, registered in the local MLflow Model Registry.
* **Orchestration (Airflow):** Chained execution workflow running nightly in an Airflow container host (5 DAGs: Ingest, Process, Transform, Quality, ML).
* **Data Warehouse (Serving):** Loader ETL streams Gold Delta tables to **Amazon Redshift Serverless** (with local **Amazon DynamoDB** serving as a low-latency real-time feature store cache).

---

## 2. Deliverables & Directory Structure

* `src/ingestion/` — Batch and streaming ingest scripts (Alpaca, FRED, News producers).
* `src/processing/` — Spark cleaning and FinBERT sentiment inference jobs.
* `src/ml/` — Model training script logging leaderboard metrics to `mlruns.db`.
* `src/backtesting/` — Strategy backtester generating comparison curve charts (`docs/backtest_equity_curve.png`).
* `src/recommendation/` — Volatility risk and model explainability engine (`docs/latest_recommendations.md`).
* `src/streaming/` — Kinesis stream producer (`aws_producer.py`) and DynamoDB consumer (`aws_consumer.py`).
* `dbt_project/` — DBT semantic models, macros, schema validations, and profiles.
* `airflow/dags/` — Nightly DAG orchestration scripts and helper operators.
* `terraform_aws/` — IaC configurations to provision all AWS services.
* `dashboard/` — Interactive BI application (`app.py`) built with Streamlit.
* `docs/` — Clean architecture file in `.excalidraw` format.

---

## 3. How to Run the Local Sandbox Demo (Offline Plan)

The platform is equipped with a fully operational local sandbox mode for demonstration:

### 1. Launch the Analytics UI (Streamlit)
To run the main dashboard showing technical charts, strategy backtests, and asset recommendations:
```bash
# Navigate to the project root and activate virtual environment
.venv\Scripts\activate

# Run the Streamlit application
streamlit run dashboard/app.py
```
Open **`http://localhost:8501`** in your browser.

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

When your cloud environment is ready, you can deploy the entire infrastructure:

### 1. Infrastructure Provisioning (Terraform)
```bash
# Navigate to terraform folder
cd terraform_aws

# Initialize and pull providers
terraform init

# Validate configuration syntax
terraform validate

# Deploy resources to AWS (provide variables)
terraform apply
```

### 2. Pipeline Execution
Update the `.env` file with the newly generated outputs from Terraform (S3 buckets, Kinesis streams, and DynamoDB connection keys).

Run the real-time stream processing tasks:
```bash
# Terminal 1: Start live Kinesis quote producer
python src/streaming/aws_producer.py

# Terminal 2: Start live DynamoDB consumer cache
python src/streaming/aws_consumer.py
```

### 3. Data Warehouse Loader
To copy the processed historical gold tables from S3 to Amazon Redshift Serverless:
```bash
python scripts/setup_redshift.py
```
This script will automatically provision the Redshift Serverless workgroup and namespace, and load the Gold features to your analytical warehouse.
