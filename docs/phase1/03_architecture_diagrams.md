# Architecture Diagrams
## Intelligent Investment Recommendation Platform

**Project:** Intelligent Investment Recommendation Platform  
**Phase:** 1 — Research & System Design  
**Document Type:** Architecture Diagrams  
**Version:** 1.0  
**Date:** June 2026  
**Audience:** Data Engineers, ML Engineers, Solution Architects  

---

## 1. High-Level System Overview

This diagram shows the complete platform at the highest level — all components and how they relate.

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║                    INTELLIGENT INVESTMENT RECOMMENDATION PLATFORM                        ║
║                              High-Level Architecture                                     ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝

 ┌──────────────────────────────────────────────────────────────────────────────────────┐
 │                           EXTERNAL DATA SOURCES                                      │
 │                                                                                      │
 │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
 │  │   Yahoo      │  │  CoinGecko   │  │    FRED      │  │  News API    │             │
 │  │  Finance     │  │  REST API    │  │  REST API    │  │  REST API    │             │
 │  │  (Equities)  │  │  (Crypto)    │  │  (Macro)     │  │  (News)      │             │
 │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
 │         │   BATCH         │   BATCH          │   BATCH         │   BATCH             │
 │         └────────────────┬┴──────────────────┴─────────────────┘                    │
 │                          │                                                            │
 │  ┌───────────────────────┴──────────────────────────────────────────────┐             │
 │  │           Alpaca WebSocket API (Real-Time Equities + Crypto)         │             │
 │  └───────────────────────┬──────────────────────────────────────────────┘             │
 │                          │   STREAMING                                                │
 └──────────────────────────┼─────────────────────────────────────────────────────────┘
                            │
          ┌─────────────────┴─────────────────┐
          │                                   │
          ▼ (Batch)                           ▼ (Stream)
 ┌─────────────────────┐           ┌─────────────────────┐
 │   BATCH PIPELINE    │           │  STREAMING PIPELINE │
 │   (Databricks)      │           │  (Kinesis +         │
 │                     │           │   Databricks)       │
 └──────────┬──────────┘           └──────────┬──────────┘
            │                                  │
            ▼                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │                    AMAZON S3  (Data Lake Storage)                │
 │                                                                  │
 │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
 │  │    BRONZE    │ → │    SILVER    │ → │     GOLD     │         │
 │  │  (Raw Data)  │   │  (Cleaned)   │   │  (Features)  │         │
 │  └──────────────┘   └──────────────┘   └──────────────┘         │
 └──────────────────────────────────────────────────────────────────┘
            │
            ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │               ML PLATFORM (Databricks + MLflow)                  │
 │                                                                  │
 │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
 │  │  Linear  │  │  Random  │  │ XGBoost  │  │  LSTM    │         │
 │  │   Reg.   │  │  Forest  │  │(Primary) │  │(Research)│         │
 │  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │
 └──────────────────────────────┬───────────────────────────────────┘
                                │
                                ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │            RECOMMENDATION ENGINE                                 │
 │                                                                  │
 │          TOP 5 ASSETS  ←──────────────────→  BOTTOM 5 ASSETS    │
 │          (Buy Signal)                        (Sell Signal)        │
 └──────────────────────────────┬───────────────────────────────────┘
                                │
                                ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │                     POWER BI DASHBOARDS                          │
 │                                                                  │
 │  Executive │  Market  │  Streaming │  ML Perf  │  Portfolio       │
 └──────────────────────────────────────────────────────────────────┘
```

---

## 2. Batch Architecture — Complete Detail

### 2.1 What Is Batch Processing?

Batch processing collects data over a defined period and processes it all at once on a schedule. Think of it like payroll — you don't pay every employee every minute they work; you calculate and pay on a schedule (weekly, bi-weekly).

For this platform, batch processing handles all **historical and non-time-critical** data.

---

### 2.2 Batch Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║                              BATCH ARCHITECTURE                                          ║
║                    Historical & Scheduled Data Processing                                ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝

SCHEDULE TRIGGERS (AWS CloudWatch Events / Databricks Scheduler)
─────────────────────────────────────────────────────────────────
  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │ Daily 11PM   │   │ Daily 11PM   │   │ Daily 6AM    │   │ Every 4 Hrs  │
  │ (Weekdays)   │   │ (Daily)      │   │ (Check new   │   │              │
  │              │   │              │   │  releases)   │   │              │
  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
         │                  │                  │                  │
         ▼                  ▼                  ▼                  ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  YAHOO FINANCE │  │   COINGECKO    │  │      FRED      │  │   NEWS API     │
│  INGESTION     │  │   INGESTION    │  │   INGESTION    │  │   INGESTION    │
│                │  │                │  │                │  │                │
│ yf.download(   │  │ cg.get_coin_   │  │ fred.get_      │  │ newsapi.get_   │
│   tickers,     │  │   ohlc_by_id() │  │   series()     │  │  everything()  │
│   start, end)  │  │                │  │                │  │                │
│                │  │  Rate limit:   │  │  Series:       │  │  Rate limit:   │
│ 50 tickers     │  │  2s sleep      │  │  FEDFUNDS      │  │  100 req/day   │
│ Auto-adjusted  │  │  between calls │  │  CPIAUCSL      │  │                │
│ Batch by 10    │  │                │  │  DGS10         │  │  Search by     │
│ tickers        │  │  10 coins      │  │  UNRATE        │  │  ticker + date │
└────────┬───────┘  └────────┬───────┘  └────────┬───────┘  └────────┬───────┘
         │                  │                  │                  │
         │ Python           │ Python           │ Python           │ Python
         │ DataFrames       │ DataFrames       │ DataFrames       │ DataFrames
         │                  │                  │                  │
         └──────────────────┴──────────────────┴──────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            INGESTION LAYER (Python + Spark)                             │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  Validation Before Write:                                                       │   │
│  │  ✓ Schema check (required columns present)                                      │   │
│  │  ✓ Row count > 0 (no empty responses)                                           │   │
│  │  ✓ Date range check (data is within expected range)                             │   │
│  │  ✓ Add metadata: ingestion_timestamp, source_name, pipeline_run_id             │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┬───────────────────────┘
                                                                  │
                                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         AMAZON S3 — BRONZE LAYER                                        │
│                         s3://investment-platform-bucket/bronze/                         │
│                                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │  bronze_stock/   │  │  bronze_crypto/  │  │  bronze_macro/   │  │ bronze_news/   │  │
│  │                  │  │                  │  │                  │  │                │  │
│  │ Partition by:    │  │ Partition by:    │  │ Partition by:    │  │ Partition by:  │  │
│  │ year/month/day   │  │ year/month/day   │  │ year/month       │  │ year/month/day │  │
│  │                  │  │                  │  │                  │  │                │  │
│  │ Format:          │  │ Format:          │  │ Format:          │  │ Format:        │  │
│  │ Delta Lake       │  │ Delta Lake       │  │ Delta Lake       │  │ Delta Lake     │  │
│  │                  │  │                  │  │                  │  │                │  │
│  │ Schema:          │  │ Schema:          │  │ Schema:          │  │ Schema:        │  │
│  │ - ticker         │  │ - coin_id        │  │ - series_id      │  │ - article_id   │  │
│  │ - date           │  │ - date           │  │ - obs_date       │  │ - ticker       │  │
│  │ - open/high/     │  │ - open/high/     │  │ - value          │  │ - title        │  │
│  │   low/close      │  │   low/close      │  │ - frequency      │  │ - content      │  │
│  │ - volume         │  │ - volume_usd     │  │ - series_name    │  │ - published_at │  │
│  │ - ingestion_ts   │  │ - market_cap     │  │ - ingestion_ts   │  │ - source_name  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  └────────────────┘  │
│                                                                                         │
│  IMPORTANT: Bronze = Immutable. Data is APPEND-ONLY. Never modify Bronze records.      │
└─────────────────────────────────────────────────────────────────┬───────────────────────┘
                                                                  │
                              DATABRICKS SCHEDULED JOB           │
                              (Triggered after Bronze write)      │
                                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                     DATABRICKS — SILVER LAYER TRANSFORMATION                            │
│                     s3://investment-platform-bucket/silver/                             │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  Quality Checks Applied:                                                        │   │
│  │  ✓ Null value handling (forward-fill prices, interpolate volume gaps)           │   │
│  │  ✓ Duplicate removal (deduplicate on ticker + date)                             │   │
│  │  ✓ Price sanity checks (close > 0, high >= low, volume >= 0)                   │   │
│  │  ✓ Schema validation (enforce column types, reject schema drift)                │   │
│  │  ✓ Outlier detection (flag 10+ sigma price moves for review)                   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │  silver_stock    │  │  silver_crypto   │  │  silver_macro    │  │  silver_news   │  │
│  │                  │  │                  │  │                  │  │                │  │
│  │ + Cleaned data   │  │ + Cleaned data   │  │ + Forward-filled │  │ + Deduped      │  │
│  │ + Split-adjusted │  │ + USD normalized │  │   macro values   │  │ + Ticker match │  │
│  │ + Trading        │  │ + 24h returns    │  │ + Release date   │  │ + Language     │  │
│  │   calendar       │  │ + Market cap     │  │   metadata       │  │   filter (en)  │  │
│  │   aligned        │  │   rank           │  │                  │  │ + Dedup by URL │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  └────────────────┘  │
│                                                                                         │
│  Implementation: Spark DataFrame API + Delta MERGE (UPSERT pattern)                    │
│  Run time: ~5-10 minutes for full refresh                                               │
└─────────────────────────────────────────────────────────────────┬───────────────────────┘
                                                                  │
                              DATABRICKS SCHEDULED JOB           │
                              (Triggered after Silver write)      │
                                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                     DATABRICKS — GOLD LAYER (FEATURE ENGINEERING)                       │
│                     s3://investment-platform-bucket/gold/                               │
│                                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │ TECHNICAL        │  │ MACRO FEATURES   │  │ SENTIMENT        │  │ TIME-SERIES    │  │
│  │ FEATURES         │  │                  │  │ FEATURES         │  │ FEATURES       │  │
│  │                  │  │ - Fed Funds Rate │  │                  │  │                │  │
│  │ - RSI (14)       │  │ - CPI YoY        │  │ - VADER score    │  │ - 1d return    │  │
│  │ - MACD           │  │ - 10Y Treasury   │  │ - FinBERT score  │  │ - 5d return    │  │
│  │ - SMA (20,50)    │  │ - Yield curve    │  │ - 3d sentiment   │  │ - Lag features │  │
│  │ - EMA (12,26)    │  │ - Unemployment   │  │   rolling avg    │  │ - Rolling vol  │  │
│  │ - ATR (14)       │  │ - VIX            │  │ - Sentiment      │  │ - 20d, 60d avg │  │
│  │ - Bollinger      │  │ - GDP growth     │  │   momentum       │  │ - Day of week  │  │
│  │ - Momentum       │  │ - M2 supply      │  │ - News volume    │  │ - Month effect │  │
│  │ - Volume ratio   │  │ - Consumer conf. │  │                  │  │                │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  └────────────────┘  │
│                                    │                                                    │
│                                    ▼                                                    │
│                         ┌──────────────────────┐                                       │
│                         │     gold_features     │                                       │
│                         │                       │                                       │
│                         │ Combined feature      │                                       │
│                         │ table: one row per    │                                       │
│                         │ (asset, date) with    │                                       │
│                         │ all features + target │                                       │
│                         │ (forward_return_5d)   │                                       │
│                         └──────────┬────────────┘                                       │
└────────────────────────────────────┼────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                     MACHINE LEARNING PLATFORM (Databricks + MLflow)                     │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │  TRAIN/VALIDATION/TEST SPLIT (Time-Series Aware)                                │   │
│  │                                                                                  │   │
│  │  ├─────────── TRAIN ────────────┤── VALIDATION ──┤── TEST ──┤                  │   │
│  │  Jan 2020              Dec 2022    Jan–Jun 2023    Jul–Dec 2023                 │   │
│  │                                                                                  │   │
│  │  NOTE: No random shuffling! Time-series splits must respect temporal order      │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │  Baseline  │  │  Random    │  │  XGBoost   │  │ LightGBM   │  │   LSTM     │       │
│  │  (Linear)  │  │  Forest    │  │ (Primary)  │  │            │  │ (Research) │       │
│  │            │  │            │  │            │  │            │  │            │       │
│  │ MLflow run │  │ MLflow run │  │ MLflow run │  │ MLflow run │  │ MLflow run │       │
│  │ Logged:    │  │ Logged:    │  │ Logged:    │  │ Logged:    │  │ Logged:    │       │
│  │ - RMSE     │  │ - RMSE     │  │ - RMSE     │  │ - RMSE     │  │ - RMSE     │       │
│  │ - MAE      │  │ - MAE      │  │ - MAE      │  │ - MAE      │  │ - MAE      │       │
│  │ - IC       │  │ - IC       │  │ - IC       │  │ - IC       │  │ - IC       │       │
│  │ - Dir Acc  │  │ - Dir Acc  │  │ - Dir Acc  │  │ - Dir Acc  │  │ - Dir Acc  │       │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  └────────────┘       │
│                                       │                                                 │
│                              Best Model Registered                                      │
│                              in MLflow Model Registry                                   │
└─────────────────────────────────────────────────────────────────┬───────────────────────┘
                                                                  │
                                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         RECOMMENDATION ENGINE + BACKTESTING                             │
│                                                                                         │
│  ┌──────────────────────────────────┐      ┌──────────────────────────────────────┐    │
│  │   WEEKLY RECOMMENDATIONS         │      │   BACKTESTING FRAMEWORK              │    │
│  │                                  │      │                                      │    │
│  │  Run every Sunday night          │      │  Simulates strategy over 5 years     │    │
│  │  for Monday market open          │      │                                      │    │
│  │                                  │      │  Metrics:                            │    │
│  │  TOP 5 → gold_recommendations    │      │  - Total return vs S&P 500/Nasdaq    │    │
│  │  BOTTOM 5 → gold_recommendations │      │  - Sharpe Ratio                      │    │
│  │                                  │      │  - Max Drawdown                      │    │
│  │  Per asset:                      │      │  - Win Rate                          │    │
│  │  - Predicted 5d return           │      │  - Calmar Ratio                      │    │
│  │  - Confidence score              │      │                                      │    │
│  │  - Risk score                    │      │  Output: backtesting_report          │    │
│  │  - Key driving features (SHAP)   │      │          (Delta table + PDF)         │    │
│  │  - Buy/Hold/Sell signal          │      │                                      │    │
│  └────────────────┬─────────────────┘      └──────────────────────────────────────┘    │
└───────────────────┼─────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              POWER BI DASHBOARDS                                        │
│                         (DirectQuery → Databricks SQL Endpoint)                         │
│                                                                                         │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │   Executive    │  │    Market      │  │   ML Model     │  │   Portfolio    │        │
│  │   Dashboard    │  │   Dashboard    │  │   Dashboard    │  │   Dashboard    │        │
│  │                │  │                │  │                │  │                │        │
│  │ - Top/Bottom 5 │  │ - Price charts │  │ - Model perf.  │  │ - Backtest     │        │
│  │ - Weekly P&L   │  │ - Technical    │  │ - Feature      │  │   results      │        │
│  │ - Risk summary │  │   indicators   │  │   importance   │  │ - Sharpe ratio │        │
│  └────────────────┘  └────────────────┘  └────────────────┘  └────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 2.3 Batch Pipeline Execution Sequence

This shows exactly **what runs, in what order, when**:

```
DAILY BATCH PIPELINE EXECUTION SEQUENCE
════════════════════════════════════════

 TIME (ET)  │  STEP  │  COMPONENT                    │  INPUT          │  OUTPUT
────────────┼────────┼───────────────────────────────┼─────────────────┼──────────────────
 4:00 PM    │   0    │  Market Close                 │  Live prices    │  Day complete
            │        │  (Trading day ends)           │                 │
────────────┼────────┼───────────────────────────────┼─────────────────┼──────────────────
 6:00 PM    │   1    │  Yahoo Finance Ingestion       │  yfinance API   │  bronze_stock
            │        │  [Databricks Job: ingest_yf]  │  (50 tickers)   │  (S3 Delta)
            │        │  Duration: ~8 min             │                 │
────────────┼────────┼───────────────────────────────┼─────────────────┼──────────────────
 6:15 PM    │   2    │  CoinGecko Ingestion           │  CG REST API   │  bronze_crypto
            │        │  [Databricks Job: ingest_cg]  │  (10 coins)     │  (S3 Delta)
            │        │  Duration: ~5 min             │                 │
────────────┼────────┼───────────────────────────────┼─────────────────┼──────────────────
 6:30 PM    │   3    │  FRED Ingestion                │  FRED API      │  bronze_macro
            │        │  [Databricks Job: ingest_fred]│  (10 series)    │  (S3 Delta)
            │        │  Duration: ~3 min             │                 │
────────────┼────────┼───────────────────────────────┼─────────────────┼──────────────────
 Every 4h   │   4    │  News API Ingestion            │  News API       │  bronze_news
  (6AM-     │        │  [Databricks Job: ingest_news]│  (business cat.)│  (S3 Delta)
  10PM)     │        │  Duration: ~2 min             │                 │
────────────┼────────┼───────────────────────────────┼─────────────────┼──────────────────
 7:00 PM    │   5    │  Silver Transformation         │  All bronze     │  silver_stock
            │        │  [Databricks Job: silver_etl] │  tables         │  silver_crypto
            │        │  Duration: ~15 min            │                 │  silver_macro
            │        │                               │                 │  silver_news
────────────┼────────┼───────────────────────────────┼─────────────────┼──────────────────
 7:30 PM    │   6    │  Feature Engineering           │  All silver     │  gold_features
            │        │  [Databricks Job: gold_feat]  │  tables         │  (S3 Delta)
            │        │  Duration: ~20 min            │                 │
────────────┼────────┼───────────────────────────────┼─────────────────┼──────────────────
 Sunday     │   7    │  Model Retraining              │  gold_features  │  MLflow model
 8:00 PM    │        │  [Databricks Job: ml_train]   │  (last 5 years) │  registry update
            │        │  Duration: ~45 min            │                 │
────────────┼────────┼───────────────────────────────┼─────────────────┼──────────────────
 Sunday     │   8    │  Recommendation Generation    │  Best model +   │  gold_recommend
 9:00 PM    │        │  [Databricks Job: recommend]  │  gold_features  │  (Top5/Bottom5)
            │        │  Duration: ~5 min             │                 │
────────────┼────────┼───────────────────────────────┼─────────────────┼──────────────────
 Monday     │   9    │  Power BI Refresh              │  gold_recommend │  Updated dashbd.
 8:00 AM    │        │  (Scheduled report refresh)   │                 │
────────────┴────────┴───────────────────────────────┴─────────────────┴──────────────────
```

---

### 2.4 S3 Bucket Structure

```
s3://investment-platform-{account-id}/
│
├── bronze/
│   ├── stock/
│   │   └── year=2024/month=06/day=10/
│   │       └── part-00000-*.parquet       ← Delta Lake files
│   ├── crypto/
│   │   └── year=2024/month=06/day=10/
│   ├── macro/
│   │   └── year=2024/month=06/
│   └── news/
│       └── year=2024/month=06/day=10/
│
├── silver/
│   ├── stock/
│   ├── crypto/
│   ├── macro/
│   └── news/
│
├── gold/
│   ├── features/                          ← gold_features table
│   ├── recommendations/                   ← gold_recommendations table
│   └── backtesting/                       ← backtesting_report table
│
└── streaming/
    └── live_market_stream/                ← Streaming Delta table
```

---

## 3. Streaming Architecture — Complete Detail

### 3.1 What Is Streaming Processing?

Streaming processes each event the moment it arrives, rather than waiting to accumulate data. The key characteristics:

- **Latency:** Seconds to minutes (not hours like batch)
- **Trigger:** Event arrival (not a clock schedule)
- **State:** Must maintain state across micro-batches
- **Fault Tolerance:** Must handle failures without data loss or duplication

---

### 3.2 Streaming Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║                              STREAMING ARCHITECTURE                                      ║
║                    Real-Time Market Data Processing                                      ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝

MARKET HOURS: 9:30 AM – 4:00 PM ET (Equities)  |  24/7 (Crypto)
──────────────────────────────────────────────────────────────────

LAYER 1: DATA SOURCE
══════════════════════
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                        ALPACA WEBSOCKET API                               │
 │                                                                          │
 │  Endpoint: wss://stream.data.alpaca.markets/v2/iex                       │
 │  Feed: IEX (free tier) — ~15ms latency                                  │
 │                                                                          │
 │  Subscriptions:                                                          │
 │  ├── bars (1-min OHLCV): All 50 equity tickers                           │
 │  ├── trades: Top 10 most liquid tickers (for volume signal)              │
 │  └── quotes (NBBO): Top 10 most liquid tickers                           │
 │                                                                          │
 │  Message Rate: ~500–2000 messages/minute during market hours             │
 │  Message Format: JSON (zlib compressed)                                  │
 └────────────────────────────────────┬─────────────────────────────────────┘
                                      │ WebSocket messages (JSON)
                                      │ ~1 msg/sec per subscribed symbol
                                      ▼

LAYER 2: PRODUCER (EVENT PUBLISHER)
════════════════════════════════════
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                    ALPACA KINESIS PRODUCER                                │
 │              [Python Script — runs on EC2 t3.micro or Lambda]            │
 │                                                                          │
 │  Responsibilities:                                                       │
 │  1. Maintain persistent WebSocket connection to Alpaca                   │
 │  2. Deserialize incoming JSON messages                                   │
 │  3. Validate message structure (T, S, o, h, l, c, v, t fields)          │
 │  4. Enrich with: received_at timestamp, producer_id                      │
 │  5. Serialize back to JSON bytes                                         │
 │  6. Call Kinesis PutRecord(s) API                                        │
 │                                                                          │
 │  Kinesis Partition Key: symbol (e.g., "AAPL")                            │
 │  → Ensures all events for the same symbol go to the same shard          │
 │  → Preserves ordering within a symbol                                    │
 │                                                                          │
 │  Error Handling:                                                         │
 │  - WebSocket disconnect → exponential backoff reconnect (1s, 2s, 4s...) │
 │  - Kinesis throttle → retry with backoff                                 │
 │  - Dead letter queue → log failed records to S3 for recovery             │
 └────────────────────────────────────┬─────────────────────────────────────┘
                                      │ PutRecord(s) API calls
                                      │ Partition key = symbol
                                      ▼

LAYER 3: MESSAGE BUS (BUFFER)
══════════════════════════════
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                     AMAZON KINESIS DATA STREAMS                           │
 │                                                                          │
 │  Stream Name: investment-platform-market-stream                          │
 │  Shard Count: 2 (handles up to 2,000 records/sec, 2MB/sec)             │
 │  Retention: 24 hours (default) — messages replay if consumer fails      │
 │  Encryption: Server-side encryption (SSE) enabled                        │
 │                                                                          │
 │  ┌─────────────┐  ┌─────────────┐                                        │
 │  │   SHARD 0   │  │   SHARD 1   │                                        │
 │  │             │  │             │                                        │
 │  │ AAPL, MSFT  │  │ NVDA, META  │                                        │
 │  │ GOOGL, AMZN │  │ TSLA, AMD   │                                        │
 │  │ ... (25 sym)│  │ ... (25 sym)│                                        │
 │  │             │  │             │                                        │
 │  │ Sequence of │  │ Sequence of │                                        │
 │  │ ordered     │  │ ordered     │                                        │
 │  │ records     │  │ records     │                                        │
 │  └─────────────┘  └─────────────┘                                        │
 │                                                                          │
 │  Cost: ~$0.015/hr per shard = ~$0.72/day for 2 shards                   │
 │  (Turns off after market hours to reduce cost)                           │
 └────────────────────────────────────┬─────────────────────────────────────┘
                                      │ GetRecords() — pull model
                                      │ (Databricks reads in micro-batches)
                                      ▼

LAYER 4: STREAM PROCESSOR (CONSUMER)
═════════════════════════════════════
 ┌──────────────────────────────────────────────────────────────────────────┐
 │              DATABRICKS STRUCTURED STREAMING JOB                         │
 │                                                                          │
 │  Notebook: /streaming/kinesis_consumer.py                                │
 │  Trigger: Continuous (processes as records arrive)                       │
 │  Micro-batch interval: Every 30 seconds                                  │
 │                                                                          │
 │  Processing Steps (per micro-batch):                                     │
 │  ┌──────────────────────────────────────────────────────────────────┐   │
 │  │ Step 1: READ from Kinesis                                        │   │
 │  │         spark.readStream.format("kinesis")                       │   │
 │  │         .option("streamName", "investment-platform-market-stream")│   │
 │  │         .option("initialPosition", "TRIM_HORIZON")              │   │
 │  │                                                                  │   │
 │  │ Step 2: PARSE JSON                                               │   │
 │  │         Deserialize binary Kinesis data → StructType schema      │   │
 │  │                                                                  │   │
 │  │ Step 3: VALIDATE                                                 │   │
 │  │         - Filter null prices                                     │   │
 │  │         - Filter malformed messages                              │   │
 │  │         - Validate timestamp is within market hours              │   │
 │  │                                                                  │   │
 │  │ Step 4: ENRICH                                                   │   │
 │  │         - Add processing_timestamp                               │   │
 │  │         - Add latency_ms (processing - event timestamp)         │   │
 │  │         - Add asset_class (equity/crypto)                       │   │
 │  │                                                                  │   │
 │  │ Step 5: WRITE to Delta table                                     │   │
 │  │         .writeStream.format("delta")                             │   │
 │  │         .outputMode("append")                                    │   │
 │  │         .option("checkpointLocation", "s3://.../checkpoints/")  │   │
 │  │         .trigger(processingTime="30 seconds")                    │   │
 │  └──────────────────────────────────────────────────────────────────┘   │
 │                                                                          │
 │  Checkpoint: S3 path stores Kinesis sequence numbers                     │
 │  → If job fails and restarts, it resumes from last checkpoint            │
 │  → Exactly-once semantics (no duplicate records)                         │
 └────────────────────────────────────┬─────────────────────────────────────┘
                                      │ writeStream → Delta
                                      ▼

LAYER 5: STREAMING DATA STORE
══════════════════════════════
 ┌──────────────────────────────────────────────────────────────────────────┐
 │              DELTA STREAMING TABLE: live_market_stream                   │
 │              s3://investment-platform-bucket/streaming/live_market_stream │
 │                                                                          │
 │  Schema:                                                                 │
 │  ┌────────────────────┬───────────────┬─────────────────────────────┐   │
 │  │  Column            │  Type         │  Description                │   │
 │  ├────────────────────┼───────────────┼─────────────────────────────┤   │
 │  │  symbol            │  STRING       │  Ticker (AAPL, BTC-USD)     │   │
 │  │  event_timestamp   │  TIMESTAMP    │  Event time from Alpaca     │   │
 │  │  processing_ts     │  TIMESTAMP    │  When Databricks processed  │   │
 │  │  open              │  DOUBLE       │  Bar open price             │   │
 │  │  high              │  DOUBLE       │  Bar high price             │   │
 │  │  low               │  DOUBLE       │  Bar low price              │   │
 │  │  close             │  DOUBLE       │  Bar close price            │   │
 │  │  volume            │  LONG         │  Shares/units traded        │   │
 │  │  vwap              │  DOUBLE       │  Volume-weighted avg price  │   │
 │  │  trade_count       │  INTEGER      │  Number of trades in bar    │   │
 │  │  latency_ms        │  INTEGER      │  End-to-end pipeline lag    │   │
 │  │  asset_class       │  STRING       │  "equity" or "crypto"       │   │
 │  └────────────────────┴───────────────┴─────────────────────────────┘   │
 │                                                                          │
 │  Partitioned by: date (for efficient time-range queries)                 │
 │  Retention: 30 days rolling (auto-expire old partitions)                 │
 │  Row growth rate: ~18,000 rows/market hour (50 symbols × 1 bar/min)     │
 └────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                  ┌───────────────────┼───────────────────┐
                  │                   │                   │
                  ▼                   ▼                   ▼
   ┌──────────────────┐  ┌────────────────────┐  ┌──────────────────────┐
   │  REAL-TIME       │  │  LIVE FEATURE      │  │  MONITORING          │
   │  POWER BI        │  │  COMPUTATION       │  │  & ALERTING          │
   │  DASHBOARD       │  │                    │  │                      │
   │                  │  │  Rolling 1h window:│  │  CloudWatch metrics: │
   │  Auto-refresh    │  │  - Current RSI     │  │  - Records/sec       │
   │  every 30 sec    │  │  - Live momentum   │  │  - Latency p95       │
   │                  │  │  - Price vs SMA    │  │  - Error count       │
   │  Shows:          │  │  - Volume anomaly  │  │  - Shard throughput  │
   │  - Live prices   │  │                    │  │                      │
   │  - Live signals  │  │  Feeds into live   │  │  Alert if:           │
   │  - Latency KPI   │  │  recommendation    │  │  - Latency > 5 min   │
   └──────────────────┘  │  updates           │  │  - No records 10min  │
                         └────────────────────┘  └──────────────────────┘
```

---

### 3.3 Event Flow — Message Lifecycle

This traces a single market event from source to dashboard:

```
SINGLE EVENT LIFECYCLE
═══════════════════════

T+0ms    │  AAPL trades at $185.30 on NYSE
         │
T+15ms   │  Alpaca receives trade from IEX feed
         │  Aggregates into 1-minute bar (running aggregate)
         │
T+60s    │  1-minute bar closes at XX:XX:00
         │  Alpaca publishes bar message to WebSocket
         │  Message: {"T":"b","S":"AAPL","o":185.20,"h":185.45,
         │           "l":185.10,"c":185.30,"v":124500,"t":"..."}
         │
T+60.1s  │  Python Producer receives WebSocket message
         │  Validates fields, adds received_at timestamp
         │  Calls Kinesis PutRecord(PartitionKey="AAPL")
         │
T+60.3s  │  Kinesis acknowledges record
         │  Assigns SequenceNumber to record
         │  Record durably stored in shard 0 (AAPL → shard 0)
         │
T+90s    │  Databricks micro-batch triggers (every 30 seconds)
         │  Reads all new Kinesis records since last checkpoint
         │  Processes batch (parse → validate → enrich → write)
         │
T+92s    │  Record written to live_market_stream Delta table
         │  Checkpoint updated in S3
         │
T+120s   │  Power BI dashboard auto-refreshes
         │  Displays AAPL latest price: $185.30
         │
Total end-to-end latency: ~60 seconds (dominated by 1-min bar aggregation)
```

---

### 3.4 Streaming vs. Batch Comparison for This Project

```
                    BATCH                          STREAMING
                    ─────                          ─────────
Latency:            Hours (data is from yesterday) Seconds (data is from now)
Use Case:           Historical analysis, ML train  Live dashboard, live signals
Data Volume:        Years of history               Current day
Fault Tolerance:    Rerun from Bronze              Kinesis 24hr replay + checkpoints
Cost Model:         Job cluster (on/off)           All-purpose cluster (running)
Complexity:         Lower                          Higher (state, exactly-once)
```

---

## 4. AWS Infrastructure Architecture

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║                            AWS INFRASTRUCTURE DIAGRAM                                    ║
╚══════════════════════════════════════════════════════════════════════════════════════════╝

 ┌────────────────────────────────────────────────────────────────────────────────────┐
 │                              AWS ACCOUNT                                           │
 │                                                                                    │
 │  ┌─────────────────────────────────────────────────────────────────────────────┐  │
 │  │                         VPC (us-east-1)                                     │  │
 │  │                                                                             │  │
 │  │  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────┐  │  │
 │  │  │  EC2 / Lambda    │    │   Kinesis Data   │    │     CloudWatch       │  │  │
 │  │  │  (Producer)      │───▶│   Streams        │    │     (Monitoring)     │  │  │
 │  │  │                  │    │                  │    │                      │  │  │
 │  │  │  t3.micro        │    │  2 Shards        │    │  - Pipeline metrics  │  │  │
 │  │  │  (free tier)     │    │  24hr retention  │◀───│  - Error alerts      │  │  │
 │  │  └──────────────────┘    └────────┬─────────┘    │  - Dashboard         │  │  │
 │  │                                   │              └──────────────────────┘  │  │
 │  │                                   │                                         │  │
 │  │  ┌────────────────────────────────┼───────────────────────────────────┐    │  │
 │  │  │              Amazon S3 (Data Lake)                                  │    │  │
 │  │  │                                                                     │    │  │
 │  │  │  Bucket: investment-platform-{account-id}                          │    │  │
 │  │  │  Region: us-east-1                                                  │    │  │
 │  │  │  Encryption: SSE-S3                                                 │    │  │
 │  │  │  Versioning: Enabled                                                │    │  │
 │  │  │  Lifecycle: Archive Bronze > 2 years to Glacier                     │    │  │
 │  │  │                                                                     │    │  │
 │  │  │  /bronze/ → /silver/ → /gold/ → /streaming/                        │    │  │
 │  │  └──────────────────────────────────────────────────────────┬──────────┘    │  │
 │  │                                                              │               │  │
 │  │  ┌───────────────────────────────────────────────────────────┼─────────────┐ │  │
 │  │  │                 IAM (Access Control)                       │             │ │  │
 │  │  │                                                            │             │ │  │
 │  │  │  Role: DatabricksRole                                      │             │ │  │
 │  │  │  Permissions: S3 read/write on investment-platform-*       │             │ │  │
 │  │  │              Kinesis GetRecords on market-stream           │             │ │  │
 │  │  │              CloudWatch PutMetricData                      │             │ │  │
 │  │  │                                                            │             │ │  │
 │  │  │  Role: ProducerRole                                        │             │ │  │
 │  │  │  Permissions: Kinesis PutRecord on market-stream           │             │ │  │
 │  │  │              CloudWatch PutMetricData                      │             │ │  │
 │  │  └─────────────────────────────────────────────────────────────────────────┘ │  │
 │  └─────────────────────────────────────────────────────────────────────────────┘  │
 │                                                                                    │
 │  ┌─────────────────────────────────────────────────────────────────────────────┐  │
 │  │                    Databricks (External to VPC — SaaS)                      │  │
 │  │                    Community Edition — databricks.com                       │  │
 │  │                    Connects to S3 via DatabricksRole                        │  │
 │  │                    Connects to Kinesis for streaming reads                  │  │
 │  └─────────────────────────────────────────────────────────────────────────────┘  │
 └────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Architecture Decisions Log

| Decision | Option A | Option B (Chosen) | Rationale |
|----------|---------|-------------------|-----------|
| Storage format | CSV / Parquet | **Delta Lake** | ACID transactions, time travel, schema enforcement |
| Stream buffer | Direct WebSocket → Databricks | **Kinesis → Databricks** | Decoupled, durable, 24hr replay |
| Batch trigger | Fixed-time scheduler | **Event-based (after Bronze write)** | Reduces latency; avoids hard-coded times |
| ML tracking | Custom logging | **MLflow** | Industry standard; built into Databricks |
| Feature store | Ad-hoc Delta tables | **Dedicated gold_features Delta table** | Single source of truth for all feature consumers |
| BI connectivity | Export to CSV | **DirectQuery via Databricks SQL** | Always-fresh data; no export lag |

---

*Document Owner: Data Engineering Team*  
*Next Document: 04_success_metrics_document.md*
