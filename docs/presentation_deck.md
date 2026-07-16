# Presentation Deck — MarketPulse Data Engineering Project
**Author:** Intern B (Azure + Databricks Hybrid Architecture)  
**Topic:** Real-Time Market Data Ingestion, Processing, ML Modeling & Data Warehousing  

---

## Slide 1: System Architecture

The following Mermaid diagram shows the complete end-to-end data flow of our implementation, from ingestion APIs to BI Dashboards and ML Model Registry:

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
    subgraph DataLake["2. Data Lake Storage (ADLS Gen2)"]
        bronze["Bronze Layer (raw_ticks / raw_macro)"]
        silver["Silver Layer (cleaned_ticks / FinBERT sentiment)"]
        gold["Gold Layer (gold_features / delta format)"]
    end

    %% Processing Layer
    subgraph Processing["3. Processing & ML (Databricks / PySpark)"]
        pyspark_jobs["PySpark Transformation Jobs"]
        mlflow["MLflow Model Registry & Leaderboard"]
        best_model["Registered RidgeRegressor (Sharpe 0.494)"]
    end

    %% Warehousing & Serving
    subgraph Serving["4. Warehousing & Serving"]
        synapse["Azure Synapse Dedicated SQL Pool (Heap Tables)"]
        sqlite_fallback["Local SQLite Fallback (analytics.db)"]
        csv_export["Exported CSV Feeds (docs/csv)"]
    end

    %% BI Layer
    subgraph BI["5. Analytics & BI (Power BI)"]
        pbi["Power BI Desktop Dashboards"]
    end

    %% Connections
    yfinance & alpaca & fred & news --> |Batch / Stream Ingest| bronze
    bronze --> |PySpark Cleaning & Validation| silver
    silver --> |FinBERT Sentiment Inference & Feature Join| gold
    gold --> |Feature Engineering| pyspark_jobs
    pyspark_jobs --> |ML Training| mlflow
    mlflow --> |Register Winning Model| best_model
    gold --> |Synapse Loader (pytds/autocommit)| synapse
    gold --> |Offline Fallback| sqlite_fallback
    sqlite_fallback --> |Materialize Feeds| csv_export
    csv_export & synapse --> |Direct Import| pbi
```

---

## Slide 2: Tech Stack Decisions

We selected a tailored, high-performance hybrid stack combining Azure-native cloud services with Databricks Spark processing:

| Layer | Selected Technology | Rationale |
| :--- | :--- | :--- |
| **Ingestion** | Event Hubs | Standard high-throughput message broker on Azure; 100% compatible with Kafka APIs. |
| **Data Lake** | ADLS Gen2 | Hierarchical namespace structure allows high-performance Big Data access patterns. |
| **Processing** | Databricks Spark | High-speed PySpark cluster execution, optimized Delta Table processing, and native MLflow integration. |
| **Warehouse** | Azure Synapse SQL | Distributed MPP SQL architecture designed for terabyte-scale enterprise analytics. |
| **BI / Serving** | Power BI / CSVs | Direct connection to Synapse SQL, with local CSV exports ensuring a 100% functional offline demo mode. |

---

## Slide 3: Cloud Cost Analysis (AWS vs. Azure)

Below is a detailed cost comparison for running the MarketPulse platform at scale (simulated at **100 million records/month**, Standard SLA, East US/East US 2 regions):

| Architectural Component | AWS Stack (Intern A) | Azure Stack (Intern B) | Cost Comparison Rationale |
| :--- | :--- | :--- | :--- |
| **Streaming Ingestion** | **Kinesis Data Streams**  <br>2 Shards = **$30.00/mo** | **Azure Event Hubs**  <br>1 TU (Standard) = **$22.32/mo** | Event Hubs Standard is slightly more cost-effective for smaller capacity units (TUs) than Kinesis shard hours. |
| **Data Lake Storage** | **Amazon S3**  <br>200 GB (Standard) = **$4.60/mo** | **ADLS Gen2**  <br>200 GB (Hot Tier) = **$4.16/mo** | Prices are nearly identical, but ADLS Gen2 metadata transactions are slightly cheaper due to hierarchical directory namespaces. |
| **Spark Processing** | **Databricks on AWS**  <br>4 DBU/hr (m5.xlarge) = **$180.00/mo** | **Databricks on Azure**  <br>4 DBU/hr (D4ds_v5) = **$176.40/mo** | Virtual machine pricing and DBU licensing are closely matched; Azure offers minor savings via enterprise discounts. |
| **Data Warehouse** | **Amazon Redshift**  <br>1 Node (ra3.xlplus) = **$795.60/mo** | **Azure Synapse (DW100c)**  <br>Dedicated Pool = **$876.00/mo** | Synapse Dedicated SQL Pool has a higher minimum entry cost ($1.20/hour for DW100c) compared to Redshift RA3 nodes. |
| **Orchestration** | **AWS MWAA (Managed Airflow)**  <br>Small Environment = **$357.00/mo** | **Azure VM Host (Self-Managed)**  <br>1 VM (B2s Standard) = **$30.36/mo** | **Massive cost saving:** Setting up Airflow in a Docker VM on Azure costs <$31/mo, whereas AWS MWAA has a high base configuration fee. |
| **Total Estimated Cost**| **$1,367.20 / month** | **$1,109.24 / month** | **Azure configuration saves ~19% ($258/month)**, primarily driven by self-managed VM orchestration. |

---

## Slide 4: Key Technical Decisions & Workarounds

*   **Pytds Driver for Synapse:** Synapse Dedicated SQL Pool is incompatible with standard `pymssql` because the driver attempts to alter session properties (such as text size) that Synapse does not support. We successfully migrated to **`python-tds` (pytds)**, which does not force these properties.
*   **Autocommit DDL Execution:** Synapse throws an error (`Operation cannot be performed within a transaction`) when creating tables. We resolved this by configuring `autocommit=True` directly at the driver level to execute table schemas outside transaction boundaries.
*   **Non-Enforced Constraints:** Synapse Dedicated SQL pools do not support standard enforced primary keys. We adjusted our DDL schemas to declare primary keys as `NONCLUSTERED NOT ENFORCED`.
*   **Heap Table storage:** Since Clustered Columnstore Indexes (Synapse's default) reject large text objects (`NVARCHAR(MAX)` used for FinBERT explainability text), we defined our warehouse tables as `HEAP` tables using `WITH (DISTRIBUTION = ROUND_ROBIN, HEAP)`.

---

## Slide 5: Lessons Learned

1. **Local Sandboxing is Crucial:** Integrating local fallbacks (SQLite for the database and MLflow storage) kept the development feedback loop incredibly fast and saved us from major blocks when the cloud subscription ended.
2. **MPP Warehouses have Strict Constraints:** Dedicated SQL pools/MPP architectures behave very differently from logical SQL databases. Constraints (Primary Keys, LOB columns, Transactions) must be configured explicitly for distributed data warehouses.
3. **Authentication & Security are Strict on Azure:** Implementing secure connection escaping (`urllib.parse.quote_plus`) and enforcing TLS encryption parameters (`cafile=certifi.where()`) are mandatory for Azure SQL resources from day one.
