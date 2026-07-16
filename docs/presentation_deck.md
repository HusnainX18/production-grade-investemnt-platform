# Presentation Deck — MarketPulse Data Engineering Project
**Author:** Intern A (AWS + Databricks Architecture)  
**Topic:** Real-Time Market Data Ingestion, Processing, ML Modeling & Data Warehousing  

---

## Slide 1: System Architecture

The following diagram shows the complete end-to-end data flow of our AWS implementation, from ingestion APIs to BI Dashboards and ML Model Registry:

```mermaid
graph TD
    %% Ingestion Layer
    subgraph Ingestion["1. Ingestion Layer"]
        yfinance["yfinance (5y Historical)"]
        alpaca["Alpaca REST / WebSockets"]
        fred["FRED API (Macro Data)"]
        news["NewsAPI (Financial Headlines)"]
    end

    %% Data Lake
    subgraph DataLake["2. Data Lake Storage (AWS S3)"]
        bronze["Bronze Layer (s3://raw_ticks)"]
        silver["Silver Layer (s3://cleaned_ticks)"]
        gold["Gold Layer (s3://gold_features)"]
    end

    %% Processing Layer
    subgraph Processing["3. Processing & ML (Databricks / PySpark)"]
        pyspark_jobs["PySpark Transformation Notebooks"]
        mlflow["MLflow Model Registry & Leaderboard"]
        best_model["Registered LSTM Regressor (Sharpe 0.037)"]
    end

    %% Warehousing & Serving
    subgraph Serving["4. Warehousing & Serving"]
        redshift["Redshift Serverless (marketpulse-wg)"]
        dynamodb["DynamoDB Feature Store (marketpulse-feature-store)"]
        sqlite_fallback["Local SQLite Fallback (mlruns.db)"]
    end

    %% BI Layer
    subgraph BI["5. Analytics & BI (QuickSight & Streamlit)"]
        qs["QuickSight Dashboards"]
        streamlit["Streamlit BI Dashboard (app.py)"]
    end

    %% Connections
    yfinance & alpaca & fred & news --> |Batch / Stream Ingest| bronze
    bronze --> |PySpark Cleaning & Validation| silver
    silver --> |Sentiment Inference & Feature Join| gold
    gold --> |Feature Engineering| pyspark_jobs
    pyspark_jobs --> |ML Training| mlflow
    mlflow --> |Register Winning Model| best_model
    gold --> |Redshift Loader (boto3 Data API)| redshift
    alpaca --> |Kinesis Streaming| dynamodb
    redshift & dynamodb & sqlite_fallback --> |Direct Connection| qs & streamlit
```

---

## Slide 2: Tech Stack Decisions

We selected a high-performance, serverless stack combining AWS-native cloud services with Databricks Spark processing:

| Layer | Selected Technology | Rationale |
| :--- | :--- | :--- |
| **Streaming** | AWS Kinesis | Serverless, on-demand partition-key ordering (per symbol) costing <$1.00/month. |
| **Data Lake** | AWS S3 | Standard object storage, secure IAM integration with Databricks instances. |
| **Processing** | Databricks Spark | High-speed PySpark cluster execution, optimized Delta Table processing, and native MLflow. |
| **Warehouse** | Redshift Serverless | Scalable MPP SQL architecture that auto-pauses when idle to prevent cluster costs. |
| **BI / Serving** | QuickSight & Streamlit | Native QuickSight Redshift connectors combined with Streamlit for real-time local UI. |

---

## Slide 3: Cloud Cost Analysis (AWS vs. Azure)

Below is a detailed cost comparison for running the MarketPulse platform at scale (simulated at **100 million records/month**, Standard SLA, us-east-1 / East US 2 regions):

| Architectural Component | AWS Stack (Intern A) | Azure Stack (Intern B) | Cost Comparison Rationale |
| :--- | :--- | :--- | :--- |
| **Streaming Ingestion** | **Kinesis Data Streams**  <br>On-Demand = **$15.00/mo** | **Azure Event Hubs**  <br>1 TU (Standard) = **$22.32/mo** | Kinesis On-Demand is cheaper for variable/bursty streaming rates compared to fixed Event Hubs TUs. |
| **Data Lake Storage** | **Amazon S3**  <br>200 GB (Standard) = **$4.60/mo** | **ADLS Gen2**  <br>200 GB (Hot Tier) = **$4.16/mo** | Prices are nearly identical; ADLS Gen2 metadata transactions are marginally cheaper. |
| **Spark Processing** | **Databricks on AWS**  <br>4 DBU/hr (m5.xlarge) = **$180.00/mo** | **Databricks on Azure**  <br>4 DBU/hr (D4ds_v5) = **$176.40/mo** | Licensing and compute rates are closely matched. |
| **Data Warehouse** | **Amazon Redshift**  <br>Serverless (minimum 8 RPU) = **$350.00/mo** | **Azure Synapse (DW100c)**  <br>Dedicated Pool = **$876.00/mo** | **AWS Advantage:** Redshift Serverless auto-pauses when idle. Synapse Dedicated Pools charge continuously unless manually paused. |
| **Orchestration** | **Docker Airflow on EC2**  <br>1 t2.micro = **$0.00/mo (Free Tier)** | **Azure VM Host (B2s)**  <br>Docker Host = **$30.36/mo** | Using local Docker Airflow or Free Tier EC2 nodes bypasses expensive managed orchestrator fees. |
| **Total Estimated Cost**| **$549.60 / month** | **$1,109.24 / month** | **AWS configuration saves ~50% ($560/month)**, primarily driven by Redshift Serverless auto-pausing. |

---

## Slide 4: Key Technical Decisions & Workarounds

*   **Delta-RS (deltalake library) for Serverless compute:** Databricks Serverless compute blocks standard JVM-level filesystem configurations (`fs.s3a.access.key`). We bypassed this by utilizing Python's Rust-backed `deltalake` library to read/write S3 files directly inside the Spark session container.
*   **Python 3.14 Compatibility Patches for dbt Core:** The environment utilizes pre-release Python 3.14 which crashes standard Pydantic V1 validation. We patched the virtual environment (`pydantic/v1/main.py` and `validators.py`) to support PEP 649 deferred annotations and treat `FieldInfo` as an arbitrary type, enabling dbt run to succeed.
*   **Redshift Serverless custom VPC subnet routing script:** Redshift Serverless requires subnets across at least 3 Availability Zones (AZs) to create a workgroup. Since the AWS account lacked a default VPC, we wrote a custom python script (`setup_redshift.py`) to dynamically provision and route extra subnets (`10.0.2.0/24` and `10.0.3.0/24`) in `us-east-1b` and `us-east-1c` to allow automated deployment.
*   **DynamoDB Online Feature Store:** SageMaker endpoints need technical indicators (RSI/MACD) in <10ms. Querying S3 gold parquet files takes seconds. We routed real-time Kinesis ticks to DynamoDB, creating a low-latency cache for Streamlit and prediction endpoints.

---

## Slide 5: Lessons Learned

1. **Auto-Shutdown configurations prevent credit burns:** Serverless compute resources (Databricks Serverless, Redshift Serverless) are cost-effective only when auto-pause parameters are set strictly (e.g., 10 minutes idle time).
2. **Local Sandboxing is Crucial:** Integrating local fallbacks (SQLite for the database and local MLflow) kept the development feedback loop fast and saved us from blocks when AWS credential limits were hit.
3. **CI/CD Push Protection prevents credential leaks:** Committing log files (like `dbt.log`) to git repositories can leak cloud API tokens. We added strict path filters to `.gitignore` and utilized Git soft-resets to clear historical logs.
