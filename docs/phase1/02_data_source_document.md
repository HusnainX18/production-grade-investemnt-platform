# Data Source Document
## Intelligent Investment Recommendation Platform

**Project:** Intelligent Investment Recommendation Platform  
**Phase:** 1 — Research & System Design  
**Document Type:** Data Source Document  
**Version:** 1.0  
**Date:** June 2026  

---

## 1. Overview

This document provides a complete technical reference for every data source used in the platform. For each source, the document covers:

- What data it provides
- Why it was selected
- How it will be accessed (API mechanics)
- Data schema and key fields
- Ingestion frequency and strategy
- Rate limits and cost considerations
- Alternative sources evaluated
- Known limitations

---

## 2. Data Source Summary

| Source | Type | Layer | Frequency | Access Method | Cost |
|--------|------|-------|-----------|---------------|------|
| Alpaca WebSocket API | Real-time streaming | Streaming | Tick / sub-second | WebSocket | Free (paper trading) |
| Yahoo Finance | Historical equities | Batch (Bronze) | Daily | `yfinance` Python library | Free |
| CoinGecko | Historical crypto | Batch (Bronze) | Daily | REST API | Free (rate limited) |
| FRED | Macroeconomic indicators | Batch (Bronze) | Monthly / Weekly | REST API | Free |
| News API | Financial news | Batch (Bronze) | Daily | REST API | Free (developer tier) |

---

## 3. Alpaca WebSocket API

### 3.1 What It Provides

Alpaca is a commission-free brokerage that exposes a WebSocket streaming API delivering real-time market data including:

- **Trade data:** Every individual trade execution (price, size, timestamp, exchange)
- **Quote data (NBBO):** Best bid and ask across exchanges
- **Bar data:** OHLCV aggregations (1-minute, 5-minute, daily)

### 3.2 Why Alpaca Was Selected

| Criterion | Alpaca | Polygon.io | IEX Cloud | Quandl |
|-----------|--------|-----------|-----------|--------|
| Real-time WebSocket | ✅ Free | ✅ Paid | ✅ Paid | ❌ |
| Paper Trading | ✅ Yes | ❌ | ❌ | ❌ |
| Crypto Support | ✅ Yes | ✅ | ❌ | ❌ |
| Developer Friendly | ✅ Excellent | ✅ Good | ✅ Good | ⚠️ Limited |
| Free Tier | ✅ Full access | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited |

**Decision:** Alpaca provides the best combination of real-time streaming, free access, and Python library support for a learning-first platform.

### 3.3 API Mechanics

**Endpoint (US Equities):**
```
wss://stream.data.alpaca.markets/v2/iex
```

**Endpoint (Crypto):**
```
wss://stream.data.alpaca.markets/v1beta3/crypto/us
```

**Authentication:**
```python
# Headers required for WebSocket handshake
{
    "action": "auth",
    "key": "ALPACA_API_KEY",
    "secret": "ALPACA_SECRET_KEY"
}
```

**Subscription Message:**
```python
{
    "action": "subscribe",
    "bars": ["AAPL", "MSFT", "NVDA"],  # 1-minute OHLCV bars
    "trades": ["AAPL"],
    "quotes": ["AAPL"]
}
```

**Sample Bar Message (Decoded JSON):**
```json
{
    "T": "b",
    "S": "AAPL",
    "o": 185.20,
    "h": 185.45,
    "l": 185.10,
    "c": 185.30,
    "v": 124500,
    "t": "2024-06-10T14:30:00Z",
    "vw": 185.28,
    "n": 342
}
```

### 3.4 Key Fields

| Field | Name | Type | Description |
|-------|------|------|-------------|
| `T` | Message Type | String | "b"=bar, "t"=trade, "q"=quote |
| `S` | Symbol | String | Asset ticker |
| `o` | Open | Float | Opening price of bar period |
| `h` | High | Float | Highest price in bar period |
| `l` | Low | Float | Lowest price in bar period |
| `c` | Close | Float | Closing price of bar period |
| `v` | Volume | Integer | Total shares traded |
| `vw` | VWAP | Float | Volume-weighted average price |
| `n` | Trade Count | Integer | Number of trades in bar |
| `t` | Timestamp | ISO 8601 | Bar start time (UTC) |

### 3.5 Ingestion Architecture

```
Alpaca WebSocket → Python Producer → Amazon Kinesis Data Stream → 
Databricks Structured Streaming → Delta Streaming Table (live_market_stream)
```

### 3.6 Rate Limits

| Tier | Connections | Subscriptions | Messages/sec |
|------|------------|---------------|--------------|
| Free (IEX) | 1 | Unlimited symbols | ~2,000/sec |

### 3.7 Known Limitations

- **Market Hours Only:** Equities stream only during market hours (9:30 AM – 4:00 PM ET)
- **IEX Feed Latency:** Free tier uses IEX feed (~15ms latency), not SIP consolidated tape
- **Crypto 24/7:** Crypto streams around the clock including weekends
- **No Historical via WebSocket:** Historical data must come from REST API or yfinance

---

## 4. Yahoo Finance (via yfinance)

### 4.1 What It Provides

Yahoo Finance is the most widely used free source for historical OHLCV data on US equities, ETFs, and crypto. The `yfinance` Python library provides a clean wrapper around Yahoo Finance's unofficial API.

**Data available:**
- Historical daily OHLCV data (up to 30+ years)
- Dividend and stock split history
- Basic fundamental data (P/E, market cap, sector)
- Options chains (not used in this project)

### 4.2 Why Yahoo Finance Was Selected

| Criterion | Yahoo Finance | Alpha Vantage | Tiingo | Quandl |
|-----------|--------------|--------------|--------|--------|
| Free Tier | ✅ Unlimited | ⚠️ 25 calls/day | ✅ 500/day | ⚠️ Limited |
| Daily OHLCV | ✅ Full history | ✅ | ✅ | ✅ |
| Python Library | ✅ `yfinance` | ✅ | ✅ | ✅ |
| Crypto Support | ✅ (BTC-USD etc.) | ❌ | ❌ | ❌ |
| Reliability | ⚠️ Unofficial API | ✅ Official | ✅ Official | ✅ Official |

**Decision:** Despite being an unofficial API, `yfinance` covers all 50 equities plus ETF benchmarks in a single library. Its community support and widespread use in data science make it the pragmatic choice.

### 4.3 API Mechanics

**Python Library:** `yfinance` (pip install yfinance)

```python
import yfinance as yf

# Download single stock
df = yf.download(
    tickers="AAPL",
    start="2020-01-01",
    end="2024-12-31",
    interval="1d",          # daily bars
    auto_adjust=True,       # adjusts for dividends/splits
    actions=True            # include dividend/split data
)

# Download multiple tickers (batch)
df = yf.download(
    tickers=["AAPL", "MSFT", "GOOGL"],
    start="2020-01-01",
    end="2024-12-31",
    interval="1d",
    group_by="ticker"       # multi-level column index
)
```

### 4.4 Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `Date` | DatetimeIndex | Trading date |
| `Open` | Float | Opening price (adjusted) |
| `High` | Float | Daily high (adjusted) |
| `Low` | Float | Daily low (adjusted) |
| `Close` | Float | Closing price (adjusted) |
| `Volume` | Integer | Total shares traded |
| `Dividends` | Float | Dividend amount (if any) |
| `Stock Splits` | Float | Split ratio (if any) |

### 4.5 Bronze Layer Schema

```
Table: bronze_stock
├── ingestion_date        TIMESTAMP
├── ticker                STRING
├── date                  DATE
├── open                  DOUBLE
├── high                  DOUBLE
├── low                   DOUBLE
├── close                 DOUBLE
├── volume                LONG
├── dividends             DOUBLE
├── stock_splits          DOUBLE
└── source                STRING ('yahoo_finance')
```

### 4.6 Ingestion Frequency

| Task | Frequency | Method |
|------|-----------|--------|
| Historical backfill | Once (at project start) | Databricks batch notebook |
| Daily refresh | Daily at 6:00 PM ET | Scheduled Databricks job |

### 4.7 Rate Limits

- Yahoo Finance does not publish official rate limits
- Community guidance: max ~2,000 requests/day safely
- **Mitigation:** Use batch downloads (multiple tickers per call), add `time.sleep(1)` between batches

### 4.8 Known Limitations

- **Unofficial API:** Yahoo Finance can change structure without notice; monitor for breaking changes
- **Data Quality:** Occasional missing values, especially around market holidays
- **No Real-Time:** Minimum delay of ~15 minutes for current price
- **Adjusted Prices:** Auto-adjustment may cause historical inconsistencies if dividends are revised

---

## 5. CoinGecko API

### 5.1 What It Provides

CoinGecko is the largest independent cryptocurrency data aggregator. It provides:

- Historical daily OHLCV data for 10,000+ cryptocurrencies
- Real-time price, market cap, volume
- Market dominance data
- Exchange volume distribution
- Developer activity metrics (GitHub commits — useful as a sentiment signal)

### 5.2 Why CoinGecko Was Selected

| Criterion | CoinGecko | CoinMarketCap | Messari | Binance API |
|-----------|----------|--------------|---------|------------|
| Free Tier | ✅ Generous | ⚠️ Limited | ⚠️ Limited | ✅ Yes |
| Historical OHLCV | ✅ Full history | ✅ | ✅ | ✅ (exchange only) |
| Python Library | ✅ `pycoingecko` | ⚠️ Community | ❌ | ✅ `python-binance` |
| Coverage | ✅ 10,000+ coins | ✅ | ⚠️ Top 500 | ⚠️ Listed on Binance |
| Developer Metrics | ✅ | ❌ | ✅ | ❌ |

**Decision:** CoinGecko's free tier covers all required assets with historical data and includes developer metrics for feature engineering.

### 5.3 API Mechanics

**Base URL:** `https://api.coingecko.com/api/v3`

**Key Endpoint — Historical OHLCV:**
```
GET /coins/{id}/ohlc?vs_currency=usd&days={days}
```

**Python Library Example:**
```python
from pycoingecko import CoinGeckoAPI

cg = CoinGeckoAPI()

# Get 365 days of OHLC data for Bitcoin
ohlc = cg.get_coin_ohlc_by_id(
    id='bitcoin',
    vs_currency='usd',
    days=365
)
# Returns: [[timestamp, open, high, low, close], ...]

# Get market chart (price, market cap, volume)
market_data = cg.get_coin_market_chart_by_id(
    id='bitcoin',
    vs_currency='usd',
    days=365,
    interval='daily'
)
```

**CoinGecko Coin IDs for Target Assets:**
```python
COINGECKO_IDS = {
    'BTC-USD': 'bitcoin',
    'ETH-USD': 'ethereum',
    'SOL-USD': 'solana',
    'BNB-USD': 'binancecoin',
    'XRP-USD': 'ripple',
    'ADA-USD': 'cardano',
    'AVAX-USD': 'avalanche-2',
    'MATIC-USD': 'matic-network',
    'LINK-USD': 'chainlink',
    'DOT-USD': 'polkadot'
}
```

### 5.4 Bronze Layer Schema

```
Table: bronze_crypto
├── ingestion_date        TIMESTAMP
├── coin_id               STRING  ('bitcoin', 'ethereum', etc.)
├── ticker                STRING  ('BTC-USD', 'ETH-USD', etc.)
├── date                  DATE
├── open                  DOUBLE
├── high                  DOUBLE
├── low                   DOUBLE
├── close                 DOUBLE
├── volume_usd            DOUBLE  (24h volume in USD)
├── market_cap_usd        DOUBLE
└── source                STRING  ('coingecko')
```

### 5.5 Rate Limits

| Tier | Calls/Min | Monthly | Cost |
|------|----------|---------|------|
| Free (Demo) | 30 | ~500K | $0 |
| Analyst | 500 | ~10M | $129/mo |

**Mitigation for Free Tier:**
```python
import time
for coin_id in COIN_IDS:
    data = cg.get_coin_ohlc_by_id(id=coin_id, ...)
    time.sleep(2)  # Stay well under 30 calls/min
```

### 5.6 Known Limitations

- **OHLC Granularity:** Daily OHLC only available for `days > 90`; hourly available for `days <= 90`
- **Historical Depth:** Some newer coins have < 2 years of history
- **Rate Limiting:** Free tier can cause 429 errors under heavy batch loads — implement exponential backoff

---

## 6. FRED (Federal Reserve Economic Data)

### 6.1 What It Provides

FRED, maintained by the Federal Reserve Bank of St. Louis, is the definitive source for macroeconomic and financial indicator data. It houses 800,000+ economic time series from 100+ sources including:

- GDP growth rates
- Inflation (CPI, PCE)
- Interest rates (Federal Funds Rate, 10-Year Treasury)
- Unemployment rate
- Consumer confidence
- Money supply (M2)

### 6.2 Why FRED Was Selected

FRED is the industry standard for macroeconomic data in quantitative finance. There is no meaningful alternative — it is the primary data source for economic indicators used by the Federal Reserve, central banks worldwide, academic economists, and quantitative analysts.

### 6.3 API Mechanics

**Python Library:** `fredapi` (pip install fredapi)

```python
from fredapi import Fred

fred = Fred(api_key='YOUR_FRED_API_KEY')

# Get Federal Funds Rate
fed_funds = fred.get_series(
    'FEDFUNDS',
    observation_start='2020-01-01',
    observation_end='2024-12-31'
)

# Get CPI
cpi = fred.get_series('CPIAUCSL', ...)  # All Urban Consumers CPI

# Get GDP Growth Rate
gdp = fred.get_series('A191RL1Q225SBEA', ...)  # Real GDP % change
```

### 6.4 Target FRED Series

| Series ID | Name | Frequency | Business Relevance |
|-----------|------|-----------|-------------------|
| `FEDFUNDS` | Federal Funds Rate | Monthly | Interest rate environment; drives equity valuations |
| `CPIAUCSL` | Consumer Price Index | Monthly | Inflation proxy; affects Fed policy |
| `UNRATE` | Unemployment Rate | Monthly | Economic health indicator |
| `DGS10` | 10-Year Treasury Yield | Daily | Risk-free rate; equity discount rate driver |
| `DGS2` | 2-Year Treasury Yield | Daily | Short-term rate expectations |
| `T10Y2Y` | 10Y-2Y Yield Spread | Daily | Recession signal (yield curve inversion) |
| `A191RL1Q225SBEA` | Real GDP Growth Rate | Quarterly | Overall economic growth |
| `M2SL` | M2 Money Supply | Monthly | Liquidity environment |
| `UMCSENT` | Consumer Sentiment | Monthly | Forward-looking demand signal |
| `VIXCLS` | VIX Volatility Index | Daily | Market fear/greed indicator |

### 6.5 Bronze Layer Schema

```
Table: bronze_macro
├── ingestion_date        TIMESTAMP
├── series_id             STRING  ('FEDFUNDS', 'CPIAUCSL', etc.)
├── series_name           STRING  ('Federal Funds Rate', etc.)
├── observation_date      DATE
├── value                 DOUBLE
├── frequency             STRING  ('daily', 'monthly', 'quarterly')
└── source                STRING  ('fred')
```

### 6.6 Ingestion Frequency

| Series | Release Frequency | Ingestion Schedule |
|--------|------------------|-------------------|
| Daily series (VIX, Treasury yields) | Daily | Daily batch job |
| Monthly series (CPI, Unemployment) | Monthly | Daily job (updates when available) |
| Quarterly series (GDP) | Quarterly | Daily job (updates when available) |

### 6.7 Rate Limits

- **Free API:** 120 requests/minute — effectively unlimited for this project
- **Registration Required:** Free API key from fred.stlouisfed.org

### 6.8 Known Limitations

- **Release Lags:** CPI releases ~2 weeks after month-end; GDP releases ~4 weeks after quarter-end — use `realtime_start` parameters for point-in-time accuracy
- **Revised Data:** Economic data is frequently revised (e.g., GDP); handle revision history carefully to avoid look-ahead bias in ML features
- **Look-Ahead Bias Risk:** Critical — when building ML features, only use data that was actually available at prediction time (use release dates, not observation dates)

---

## 7. News API

### 7.1 What It Provides

News API aggregates articles from 80,000+ news sources and blogs. For financial analysis, it provides:

- Top business and financial news headlines
- Full article text (publisher-permitting)
- Source metadata (publisher, author, URL)
- Publication timestamps

### 7.2 Why News API Was Selected

| Criterion | News API | GDELT | Bloomberg API | Reuters API |
|-----------|---------|-------|--------------|------------|
| Free Tier | ✅ 100 req/day | ✅ Free | ❌ Enterprise | ❌ Enterprise |
| Python Library | ✅ `newsapi-python` | ⚠️ Custom | N/A | N/A |
| Quality | ✅ Good | ⚠️ Variable | ✅ Premium | ✅ Premium |
| Financial Focus | ✅ Business category | ⚠️ General | ✅ Full focus | ✅ Full focus |

**Decision:** News API's developer tier is free and sufficient for a learning project. For production, upgrading to a paid financial news provider (Bloomberg, Refinitiv) would be recommended.

### 7.3 API Mechanics

**Python Library:** `newsapi-python` (pip install newsapi-python)

```python
from newsapi import NewsApiClient

newsapi = NewsApiClient(api_key='YOUR_NEWS_API_KEY')

# Fetch business headlines
headlines = newsapi.get_top_headlines(
    category='business',
    language='en',
    country='us',
    page_size=100
)

# Search for ticker-specific news
aapl_news = newsapi.get_everything(
    q='Apple AAPL stock',
    from_param='2024-06-01',
    to='2024-06-10',
    language='en',
    sort_by='relevancy',
    page_size=100
)
```

**Sample Response:**
```json
{
    "status": "ok",
    "totalResults": 847,
    "articles": [{
        "source": {"id": "reuters", "name": "Reuters"},
        "author": "Jane Smith",
        "title": "Apple Reports Record Q4 Earnings Beating Analyst Estimates",
        "description": "Apple Inc. reported its quarterly earnings...",
        "url": "https://reuters.com/...",
        "publishedAt": "2024-06-10T14:30:00Z",
        "content": "Full article text..."
    }]
}
```

### 7.4 Bronze Layer Schema

```
Table: bronze_news
├── ingestion_date        TIMESTAMP
├── article_id            STRING  (MD5 hash of URL — dedup key)
├── ticker                STRING  (target asset, if matched)
├── source_name           STRING
├── author                STRING
├── title                 STRING
├── description           STRING
├── url                   STRING
├── published_at          TIMESTAMP
├── content               STRING
└── source                STRING  ('newsapi')
```

### 7.5 Sentiment Processing (Preview — Full Detail in Phase 7)

Raw news text will be processed using:

1. **VADER Sentiment Analyzer** — Rule-based, fast, well-calibrated for financial short-form text
2. **FinBERT** — BERT model fine-tuned on financial text (higher accuracy, higher compute cost)

```python
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from transformers import pipeline

# VADER (fast, baseline)
analyzer = SentimentIntensityAnalyzer()
score = analyzer.polarity_scores("Apple beats earnings expectations")
# Returns: {'neg': 0.0, 'neu': 0.21, 'pos': 0.79, 'compound': 0.8316}

# FinBERT (accurate, slower)
finbert = pipeline("sentiment-analysis", model="ProsusAI/finbert")
result = finbert("Apple beats earnings expectations")
# Returns: [{'label': 'positive', 'score': 0.9876}]
```

### 7.6 Rate Limits

| Tier | Requests/Day | Historical Depth | Cost |
|------|-------------|-----------------|------|
| Developer (Free) | 100 | 1 month | $0 |
| Business | 250 | 1 year | $449/mo |
| Enterprise | Unlimited | 5 years | Custom |

**Mitigation:** For historical backfill beyond 1 month, use publicly available news datasets (e.g., Kaggle financial news datasets, GDELT) combined with News API for ongoing daily collection.

### 7.7 Known Limitations

- **1-Month Historical Limit (Free):** Cannot access news older than 30 days on free tier
- **100 Req/Day Limit:** Constrains per-ticker search granularity
- **Content Truncation:** `content` field is truncated to first 200 characters by default
- **Source Bias:** Aggregator may over-represent certain publishers

---

## 8. Data Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                              │
│                                                              │
│  [Alpaca WebSocket] → REAL-TIME → [Amazon Kinesis]          │
│                                                              │
│  [Yahoo Finance]   ┐                                         │
│  [CoinGecko]       ├──→ BATCH → [S3 Bronze Zone]            │
│  [FRED]            │         → [Databricks Bronze Tables]    │
│  [News API]        ┘                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. API Key Management

All API keys will be stored as:
- **Databricks Secrets** (for Databricks notebooks)
- **AWS Secrets Manager** (for Lambda/EC2 producers)

Keys required:
| Service | Key Name | Where to Register |
|---------|----------|-------------------|
| Alpaca | `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` | alpaca.markets (free paper account) |
| FRED | `FRED_API_KEY` | fred.stlouisfed.org/docs/api/ |
| News API | `NEWS_API_KEY` | newsapi.org (free developer account) |
| CoinGecko | Optional (higher rate limits with key) | coingecko.com/en/api |

---

*Document Owner: Data Engineering Team*  
*Next Document: 03_architecture_diagram.md*
