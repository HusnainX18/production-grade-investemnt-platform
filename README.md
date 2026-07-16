# MarketPulse — Data Engineering & Algorithmic Trading Platform (AWS + Databricks)
**Author:** Intern A (AWS + Databricks Stack)  
**Project Scope:** Ingest, process, transform, and analyze real-time stock and cryptocurrency market data, train machine learning models, and orchestrate the pipeline at scale.

---

## 1. System Architecture

MarketPulse utilizes a modern serverless Medallion Lakehouse architecture deployed on AWS:

*   **Ingestion (Bronze):** Batch historical data ingestion using `yfinance` and streaming ticks using `Alpaca WebSockets` into **AWS S3** via **AWS Kinesis**.
*   **Processing (Silver):** PySpark processing on Databricks to clean, deduplicate, validate schemas, and run news sentiment inference.
*   **Analytics Feature Store (Gold):** Aggregated metrics, technical indicators (RSI, MACD, Bollinger Bands), and macro indicators loaded to Delta tables.
*   **Machine Learning (MLflow):** LSTM regressor model trained on gold features to predict price movements, registered in the local MLflow Model Registry.
*   **Orchestration (Airflow):** Chained execution workflow running daily in local Docker containers (re-routed from EC2 to bypass host pathing).
*   **Data Warehouse (Serving):** Loader ETL streams Gold Delta tables to **Amazon Redshift Serverless** (with local **DynamoDB Online Feature Store** cache).

---

## 2. Directory Structure

*   `src/ingestion/` — Ingestion scripts for stock, crypto, news, and macro data.
*   `src/processing/` — Spark cleaning and medallion layer transformation scripts.
*   `src/ml/` — Model training script logging metrics to `mlruns.db`.
*   `src/backtesting/` — Strategy backtester generating comparison metrics.
*   `src/recommendation/` — Volatility risk and model explainability engine.
*   `src/streaming/` — Kinesis stream producer and DynamoDB cache consumer.
*   `dbt_project/` — dbt models, macros, schema validations, and profiles.
*   `airflow/dags/` — Orchestration DAGs for ingestion, processing, dbt, quality, and ML training.
*   `terraform_aws/` — IaC configurations to provision AWS resources.
*   `docs/` — Clean architecture file in `.excalidraw` format.

---

## 3. How to Run the Platform Demo

### 1. Launch the Analytics UI (Streamlit)
To run the main dashboard showing technical charts, strategy backtests, and asset recommendations:
```bash
# Navigate to the project root and activate virtual environment
.venv\Scripts\activate

# Run the Streamlit application
streamlit run dashboard/app.py
```
Open **`http://localhost:8501`** in your browser.

### 2. Launch the Orchestrator (Airflow)
To start the pipeline scheduler and execute the DAGs:
```bash
# Navigate to the airflow directory and launch Docker
cd airflow
docker compose up --build -d
```
Open **`http://localhost:8081`** and log in with username/password: `admin` / `admin`.

### 3. Start Live Streaming Tick Data
To stream Alpaca quotes in real-time through Kinesis into the DynamoDB sidebar cache:
```bash
# Open two separate terminals (with virtual env active) and run:
python src/streaming/aws_producer.py
python src/streaming/aws_consumer.py
```

---

## 4. Production Cloud Deployment (Terraform)

Deploy all AWS infrastructure via IaC:
```bash
cd terraform_aws
terraform init
terraform validate
terraform apply
```
Update your local `.env` variables with the outputs from Terraform to route data to S3, Kinesis, DynamoDB, and Redshift.
