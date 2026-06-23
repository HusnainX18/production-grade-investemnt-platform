# Phase 3 — Batch Ingestion Pipeline (Bronze Layer)
## Completion Document

**Project:** Intelligent Investment Recommendation Platform
**Phase:** 3 — Batch Ingestion Pipeline
**Status:** ✅ COMPLETE
**Completed:** June 2026

---

## What We Built

Phase 3 established the raw data foundation of the entire platform.
We wrote 4 Python ingestion scripts that pull historical financial data
from 3 different APIs and store it in the S3 Bronze layer as Delta tables.

---

## Bronze Layer Final State

| Table | Rows | Null % | S3 Path | Status |
|-------|------|--------|---------|--------|
| Stocks | 62,593 | 0.00% | bronze/stocks | ✅ Healthy |
| Crypto | 12,459 | 0.00% | bronze/crypto | ✅ Healthy |
| Macro | 6,520 | 0.00% | bronze/macro | ✅ Healthy |
| News | 612 | 0.20% | bronze/news | ✅ Healthy |
| **TOTAL** | **82,184** | **~0.01%** | | **✅ All Healthy** |

---

## Scripts Written

| Script | Source | Data |
|--------|--------|------|
| `src/ingestion/ingest_stocks.py` | Alpaca IEX | 50 equities × 5yr daily bars |
| `src/ingestion/ingest_crypto.py` | Alpaca Crypto | 9 crypto assets × 5yr daily bars |
| `src/ingestion/ingest_macro.py` | FRED API | 10 macroeconomic indicators |
| `src/ingestion/ingest_news.py` | News API | 612 financial news articles |
| `src/utils/verify_bronze.py` | (verification) | Health check across all 4 tables |

---

## Data Sources Used

| Source | API | Key Required | Rate Limit |
|--------|-----|-------------|------------|
| Alpaca Markets | `alpaca-py` SDK | Yes (stocks) / No (crypto) | 200 req/min |
| FRED (Federal Reserve) | REST API | Yes | 120 req/min |
| News API | REST API | Yes | 100 req/day (free) |

---

## Key Technical Decisions Made in This Phase

### 1. Replaced Yahoo Finance + CoinGecko with Alpaca
**Why:** Using a single source for both historical equity data and real-time
streaming eliminates Train-Serve Skew — the dangerous condition where a model
trains on data from one source but gets predictions from a different source
with slightly different prices, timestamps, and schema.

### 2. Replaced CoinGecko with Alpaca Crypto
**Why:** Same schema as equity data (OHLCV + vwap + trade_count), zero
configuration, no API key required. BNB/USD was not available on the free
Alpaca crypto feed — 9 assets remain.

### 3. Used IEX Feed Instead of SIP Feed for Stocks
**Why:** Alpaca's free tier only permits the IEX exchange feed, not the
consolidated SIP (Securities Information Processor) feed from all exchanges.
IEX data is professional quality and fully sufficient for our ML use case.
Error encountered: `"subscription does not permit querying recent SIP data"`
Fix: Added `feed=DataFeed.IEX` to the `StockBarsRequest`.

### 4. Used `deltalake` Python Library (Not PySpark S3A)
**Why:** Databricks Free Edition uses Spark Connect, which blocks JVM-level
Hadoop configuration (`spark.conf.set("fs.s3a.access.key", ...)`). The Python
`deltalake` library (delta-rs) writes Delta tables directly to S3 using the
AWS SDK, bypassing Spark Connect entirely. Verified working in Phase 2.

### 5. News API Free Tier — 30 Days Only
**Why:** The News API free developer plan limits historical search to the
last 30 days. This is acceptable because news sentiment is most impactful
for recent data. Articles collected: 612 across 233 sources.
The 0.20% null rate in news data is from articles with missing descriptions
(normal — some articles omit this field).

---

## Data Schema Reference

### Stocks & Crypto (identical schema)
```
symbol           | string  | Ticker or trading pair (e.g. AAPL, BTC/USD)
timestamp        | string  | Bar date (UTC)
open             | float   | Opening price
high             | float   | Daily high
low              | float   | Daily low
close            | float   | Closing price
volume           | float   | Volume traded
trade_count      | int     | Number of trades
vwap             | float   | Volume-weighted average price
ingestion_timestamp | string | When this row was ingested
data_source      | string  | "alpaca"
asset_class      | string  | "equity" or "crypto"
```

### Macro
```
date             | string  | Observation date
value            | float   | Indicator value
series_id        | string  | FRED series code (e.g. FEDFUNDS)
series_name      | string  | Human-readable name
ingestion_timestamp | string | When ingested
data_source      | string  | "fred"
```

### News
```
title            | string  | Article headline
description      | string  | Article summary
url              | string  | Source URL
source           | string  | Publisher name
published_at     | string  | Publication datetime
query_tickers    | string  | Comma-separated tickers this query covers
ingestion_timestamp | string | When ingested
data_source      | string  | "newsapi"
```

---

## What Comes Next

**Phase 4 — Real-Time Streaming (Kinesis)**
- Alpaca WebSocket producer pushes live market ticks to Kinesis
- Databricks serverless notebook consumes from Kinesis
- Live data lands in `streaming/live_market_stream` Delta table

**Phase 5 — Silver Layer + Great Expectations**
- Clean, deduplicate, and validate all Bronze data
- Run 10+ Great Expectations quality checks
- Produce Silver-layer Delta tables ready for feature engineering
