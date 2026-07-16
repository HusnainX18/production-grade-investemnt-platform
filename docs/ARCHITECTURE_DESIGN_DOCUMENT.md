# Architecture Design Document (ADD) & Architecture Decision Records (ADRs)

**Project:** MarketPulse — Quantitative Trading & MLOps Platform  
**Date:** 2026-07-15  
**Author:** Platform Engineering Team  

---

## 1. Architectural Overview & Pillars
MarketPulse implements a hybrid **Lambda Architecture** designed for high-frequency algorithmic quantitative trading. The architecture separates concerns into:
1.  **Batch Layer (Offline Path):** Aggregates news sentiment, macro indicators, and daily historical pricing to train ML models.
2.  **Speed Layer (Online Path):** Evaluates live stock and crypto tick data under 50ms latency using serverless compute.
3.  **Serving Layer (Data Warehouse):** Exposes clean datasets and strategy backtest results for visualization (Power BI).

---

## 2. Alternatives Considered & Evaluated

### Alternative A: The Databricks & Snowflake Enterprise Stack
*   **Design:** Use Databricks for all Spark-based ETL and ML model training (MLflow), Snowflake as the main Data Warehouse, and Confluent Kafka for real-time ingestion.
*   **Why we did NOT choose it:** 
    *   **Cost:** Snowflake and Databricks charge heavy compute fees per second. Confluent Kafka has a base cluster cost of ~$250/mo. For our initial sandbox scale, this would exceed our $80/mo budget within days.
    *   **Complexity:** Databricks requires maintaining cluster configurations, which is excessive for small-volume stock tickers.

### Alternative B: The All-in-One PostgreSQL / TimescaleDB Stack
*   **Design:** Store all raw ticks, historical news, macro indicators, and ML model outputs in a single TimescaleDB instance. Write Python scripts on a single server to handle training and predictions.
*   **Why we did NOT choose it:**
    *   **Single Point of Failure:** Scaling, training, and predicting on a single database CPU will lead to locking, table exhaustion, and API timeouts.
    *   **Lack of ML Governance:** It does not support model registries, experiment tracking (MLflow), or serverless scaling.

---

## 3. Architecture Decision Records (ADRs)

### ADR-001: Database Selection (Local SQLite vs. Production RDS PostgreSQL)
*   **Status:** Approved
*   **Context:** Streamlit needs to load tables quickly. During local sandbox development, configuring a Postgres server creates overhead, but in cloud production, SQLite cannot support concurrent writes.
*   **Decision:** We implemented a dual-mode database driver. Locally, the system loads tables into a fast local `analytics.db` (SQLite) file. In production, we deploy a cost-optimized **Amazon RDS PostgreSQL (db.t3.micro)** instance. This keeps development fast while ensuring production concurrency.

### ADR-002: Real-Time Cache Selection (DynamoDB vs. Redis Cache)
*   **Status:** Approved
*   **Context:** The SageMaker Endpoint must enrich incoming stock price ticks with technical indicators (e.g., 50d SMA) in under 10ms. Querying S3 Gold parquet files takes 2-5 seconds.
*   **Decision:** We chose **Amazon DynamoDB** as our online feature store. We rejected Redis (ElastiCache) because Redis has a fixed base server cost of $100+/mo. DynamoDB offers single-digit millisecond reads, integrates natively with SageMaker, and has a generous free tier of 25 GB.

### ADR-003: ML Endpoint Hosting (SageMaker Serverless vs. Dedicated Real-Time GPU)
*   **Status:** Approved
*   **Context:** Deployed models must process trades during market hours (9:30 AM - 4:00 PM EST) but sit idle at night.
*   **Decision:** We deployed a **SageMaker Serverless Endpoint** instead of a dedicated GPU instance (`ml.g4dn`). Serverless endpoints scale down to zero when the market is closed, charging us strictly per-millisecond of inference. This keeps monthly hosting costs below $0.10.

### ADR-004: Ingestion Broker (AWS Kinesis vs. Apache Kafka)
*   **Status:** Approved
*   **Context:** We need a streaming broker to ingest live Alpaca price feeds.
*   **Decision:** We selected **AWS Kinesis Streams in On-Demand Mode**. Unlike Kafka (which requires setting up clusters, brokers, and zookeeper instances), Kinesis is fully managed, serverless, and scales dynamically, costing `<$1.00/month`.

### ADR-005: Pipeline Orchestration (Docker Airflow on EC2 vs. AWS MWAA)
*   **Status:** Approved
*   **Context:** We need an orchestrator to schedule our ingestion, ETL, and ML training pipelines in sequence.
*   **Decision:** We deployed **Apache Airflow using Docker Compose on a single t3.small EC2 instance**. We rejected AWS MWAA because MWAA costs a minimum of $150/month. A self-hosted Docker container runs the exact same code, supports the same DAGs, and exposes the same Web UI for only $15/month.
