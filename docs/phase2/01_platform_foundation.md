# Phase 2 — Data Platform Foundation Document

**Project:** Intelligent Investment Recommendation Platform  
**Phase:** 2 — Data Platform Foundation  
**Document Type:** Architecture & Technology Decisions  
**Version:** 1.0  
**Date:** June 2026  

---

## 1. What We Did in Phase 2 (Summary)
In Phase 2, we successfully set up the entire cloud and local infrastructure required to ingest, process, and store financial data. Specifically, we completed:
1. **AWS Cloud Storage & Streaming Setup:** Created an S3 bucket with 6 architectural folders (Medallion layers), set up IAM users/roles for secure access, provisioned a 2-shard Kinesis Stream for real-time market data, and established a CloudWatch billing safety alarm.
2. **Databricks Environment Setup:** Logged into Databricks Free Edition (Serverless) and established a structured workspace matching our local project directories. We verified that we can write high-performance Delta Lake tables directly to S3.
3. **Local Code Repository Setup:** Created our workspace directory structure, set up a virtual python environment, configured standard dependencies in `requirements.txt`, and loaded our configurations (`config.yaml` and `.env`) to successfully test local-to-cloud connectivity.

---

## 2. Technologies Used, Why, and Alternatives

This section explains the technical decisions we made for each core component, the alternatives we considered, and why we chose our current setup.

### 2.1 Storage Layer: Amazon S3 (Simple Storage Service)
We chose S3 to host our data lake. It is structured into folders representing the Medallion Architecture:
*   `bronze/` - Raw data directly from APIs.
*   `silver/` - Cleaned and normalized tables.
*   `gold/` - Feature-engineered data ready for ML models.

*   **Why we used S3:** It is cheap (pennies per gigabyte), infinitely scalable, offers 99.999999999% durability, and integrates natively with Apache Spark and Python libraries.
*   **Alternatives considered:**
    *   *Local hard drive storage:* Rejected because local files are lost if the computer crashes or when Databricks serverless compute restarts.
    *   *Relational Database (e.g., PostgreSQL):* Rejected because relational databases do not handle raw, unstructured files (like raw API JSON responses) well and are expensive to scale for high-velocity streaming data.
    *   *Google Cloud Storage (GCS) or Azure Blobs:* Rejected because we are building our pipeline on AWS. Using S3 prevents cross-cloud data transfer fees.

---

### 2.2 Streaming Buffer: Amazon Kinesis Data Streams
We provisioned a Kinesis Stream with 2 shards to buffer real-time market data from the Alpaca WebSocket.
*   **Why we used Kinesis:** It is a fully managed AWS service. A 2-shard stream is incredibly cheap (~$0.72/day) and requires zero infrastructure management. It guarantees that if our Databricks processing job goes down, Kinesis will safely buffer our streaming data for up to 24 hours so we don't lose a single stock price.
*   **Alternatives considered:**
    *   *Apache Kafka (Self-hosted on EC2):* Rejected because setting up and managing a Kafka cluster is complex and requires significant manual maintenance.
    *   *Managed Streaming for Apache Kafka (Amazon MSK):* Rejected because it is expensive (~$100+/month minimum), which is overkill for our small-scale learning project.
    *   *Direct WebSocket to Databricks:* Rejected because if Databricks restarts or goes offline, the direct connection breaks and any market data sent during the downtime is permanently lost.

---

### 2.3 Compute Platform: Databricks Free Edition (Serverless)
We set up a workspace on the newly upgraded Databricks Free Edition.
*   **Why we used it:** It is free, provides an excellent notebook interface, and handles cluster resource management serverlessly (meaning no waiting for clusters to start). It natively supports Delta Lake and MLflow (which we will use for model tracking).
*   **Alternatives considered:**
    *   *Local Jupyter Notebooks only:* Rejected because local machines lack the collaborative workspace features and cannot easily scale if our dataset grows.
    *   *AWS EMR (Elastic MapReduce):* Rejected because EMR costs money to run EC2 clusters, whereas Databricks Free Edition is 100% free.
    *   *Snowflake:* Rejected because Snowflake is a cloud data warehouse optimized for SQL, making it less native and more expensive for custom Python-based ML training compared to Databricks.

---

### 2.4 Data Access Method: Boto3 & Delta-RS (`deltalake`)
We verified that we can write Delta tables directly to S3 using the Python `deltalake` library configured with AWS credentials.
*   **Why we used it:** Databricks Serverless uses **Spark Connect**, a modern protocol that separates the client JVM from the execution cluster. As a result, classic Spark-JVM configuration methods like `spark.conf.set("fs.s3a.access.key", ...)` are blocked. Using standard Python libraries (`boto3` and `deltalake`) allows us to write directly to S3 from the driver node, bypassing Spark Connect limits while still utilizing high-performance Delta formats.
*   **Alternatives considered:**
    *   *Legacy DBFS Mounts (`dbutils.fs.mount`):* Rejected because mounts are deprecated and completely blocked in Databricks Serverless.
    *   *Unity Catalog External Locations:* Rejected because configuring Unity Catalog requires enterprise-level admin privileges and AWS-Databricks cross-account IAM integrations which are not supported on the Databricks Free Edition metastore.
