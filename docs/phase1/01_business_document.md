# Business Document
## Intelligent Investment Recommendation Platform

**Project:** Intelligent Investment Recommendation Platform  
**Phase:** 1 — Research & System Design  
**Document Type:** Business Document  
**Version:** 1.0  
**Date:** June 2026  
**Audience:** Data Engineers, ML Engineers, Business Stakeholders  

---

## 1. Executive Summary

This document defines the business context, prediction objective, problem framing, and analytical scope for the Intelligent Investment Recommendation Platform. It establishes the foundational understanding that guides every engineering and machine learning decision made throughout the project lifecycle.

---

## 2. Business Problem Statement

### 2.1 The Challenge

Financial markets generate enormous volumes of data every second. Retail and institutional investors must synthesize price movements, trading volumes, macroeconomic shifts, sentiment signals, and news events to make investment decisions — a task far beyond human cognitive capacity when applied across hundreds of assets simultaneously.

**The core problem has three dimensions:**

| Dimension | Description | Consequence of Ignoring |
|-----------|-------------|------------------------|
| **Volume** | Thousands of assets across equities and crypto | Decision paralysis or random selection |
| **Velocity** | Prices update tick-by-tick; news breaks instantly | Stale recommendations by the time they are acted on |
| **Variety** | Price data, macro indicators, sentiment, news | Incomplete picture → poor predictions |

### 2.2 Why Existing Solutions Fall Short

- **Manual analysis** cannot scale across 50+ equities and major crypto assets simultaneously
- **Rule-based systems** (e.g., "buy when RSI < 30") are brittle and do not adapt to changing market regimes
- **Single data source** platforms miss the cross-asset, cross-signal correlations that drive real price movements
- **Black-box predictions** without explainability are rejected by professional investors who need justification for trades

---

## 3. Prediction Objective Decision

### 3.1 Candidate Prediction Targets

The following prediction horizons were evaluated:

| Target | Time Horizon | Type | Pros | Cons |
|--------|-------------|------|------|------|
| **Next-Day Return** | T+1 | Regression | High data density; actionable immediately | High noise; markets are nearly efficient at daily level |
| **Next-Week Return** | T+5 | Regression | Balances signal and noise; operationally feasible | Still noisy; requires frequent retraining |
| **Next-Month Return** | T+22 | Regression | Stronger macro signal; smoother predictions | Fewer training samples; slow feedback loop |
| **Buy/Hold/Sell** | T+5 or T+22 | Classification | Interpretable; directly actionable | Threshold selection is arbitrary; masks return magnitude |
| **Risk-Adjusted Return** | T+22 | Regression | Captures Sharpe-like signal | Complex label engineering; hard to validate |

### 3.2 ✅ Recommended Prediction Target: Next-Week Return (T+5)

**Decision:** The primary prediction target is the **5-day forward return** (next-week return), defined as:

```
Forward_Return(t) = (Close(t+5) - Close(t)) / Close(t)
```

**Justification:**

1. **Signal-to-Noise Balance:** Weekly returns contain sufficient signal from technical and macro factors without the extreme noise of single-day price movements
2. **Operational Realism:** Recommendations generated on Monday can realistically be acted upon by investors within the same week
3. **Training Sample Density:** With 5 years of daily data (~1,250 observations per asset), T+5 provides enough non-overlapping samples for robust model training
4. **Industry Alignment:** Weekly rebalancing is the most common strategy in quantitative hedge fund frameworks (Renaissance Technologies, AQR, Two Sigma all reference weekly holding periods as primary backtesting unit)
5. **Feature Relevance:** RSI, MACD, sentiment trends, and macro releases all have documented 3–7 day lag effects in academic finance literature

### 3.3 Secondary Prediction Target: Buy/Hold/Sell Classification

A secondary classification output will be derived from the regression output by thresholding:

```
BUY  if predicted_return > +1.5%
SELL if predicted_return < -1.5%
HOLD otherwise
```

This provides business-friendly labels for the dashboard while retaining the full quantitative signal for ranking.

### 3.4 Why Not Monthly?

Monthly predictions were evaluated and rejected for the following reasons:
- With 5 years of data, monthly predictions yield only ~60 non-overlapping samples per asset — insufficient for reliable ML training
- Model feedback cycles are too slow to detect regime changes
- Operational: monthly recommendations cannot compete with weekly-rebalancing benchmark funds

### 3.5 Why Not Daily?

Daily predictions were evaluated and rejected for the following reasons:
- The Efficient Market Hypothesis (weak form) strongly suggests daily price movements are largely unpredictable
- Extreme noise-to-signal ratio degrades model accuracy to near-random performance
- Transaction costs erode any marginal edge at daily frequency
- Requires near-real-time feature computation at a cost prohibitive for Databricks Community Edition

---

## 4. What Are We Predicting? — Formal Definition

### 4.1 Primary Target Variable

**Variable Name:** `forward_return_5d`  
**Definition:** Percentage price return over the next 5 trading days  
**Formula:**
```
forward_return_5d(t) = (Price(t+5) − Price(t)) / Price(t) × 100
```
**Unit:** Percentage (%)  
**Type:** Continuous (Regression)  
**Range:** Theoretically unbounded; practically -30% to +30% for weekly returns  

### 4.2 Derived Classification Label

**Variable Name:** `signal`  
**Values:** BUY (1), HOLD (0), SELL (-1)  
**Derived from:** Thresholding `forward_return_5d`  
**Business meaning:** Directly actionable trading signal for the dashboard  

### 4.3 Ranking Score

**Variable Name:** `opportunity_score`  
**Definition:** Composite ranking score combining:
- Predicted 5-day return (50% weight)
- Prediction confidence (20% weight)
- Risk-adjusted expectation: predicted_return / rolling_volatility_20d (20% weight)
- Sentiment score (10% weight)

**Purpose:** Generates the Top 5 / Bottom 5 ranked recommendations

---

## 5. Asset Universe

### 5.1 Equities (~50 Stocks)

Selected to provide broad sector coverage and sufficient liquidity for reliable market data:

| Sector | Representative Assets |
|--------|----------------------|
| Technology | AAPL, MSFT, GOOGL, NVDA, META, AMZN, TSLA, AMD, INTC, CRM |
| Financial Services | JPM, BAC, GS, MS, WFC, BLK, V, MA, AXP, C |
| Healthcare | JNJ, UNH, PFE, ABBV, MRK, CVS, LLY, TMO, MDT, AMGN |
| Consumer Goods | PG, KO, PEP, WMT, COST, HD, NKE, MCD, SBUX, TGT |
| Energy | XOM, CVX, COP, SLB, EOG, PXD, MPC, VLO, PSX, HES |

### 5.2 Cryptocurrencies (~10 Assets)

| Asset | Ticker | Rationale |
|-------|--------|-----------|
| Bitcoin | BTC-USD | Market leader; macro proxy |
| Ethereum | ETH-USD | Ecosystem and DeFi signal |
| Solana | SOL-USD | High-volatility alpha opportunity |
| Binance Coin | BNB-USD | Exchange liquidity proxy |
| XRP | XRP-USD | Regulatory risk signal |
| Cardano | ADA-USD | Alternative Layer 1 |
| Avalanche | AVAX-USD | Ecosystem growth signal |
| Polygon | MATIC-USD | Scalability play |
| Chainlink | LINK-USD | Oracle infrastructure |
| Polkadot | DOT-USD | Interoperability thesis |

---

## 6. Analytical Scope

### 6.1 Historical Lookback Period
- **Minimum:** 5 years of daily data (January 2020 – Present)
- **Rationale:** Covers bull market (2020–2021), bear market (2022), and recovery (2023–2024), ensuring model exposure to multiple market regimes

### 6.2 Feature Engineering Scope
All features are derived from raw data and transformed for ML consumption. Full feature set is documented in Phase 7.

### 6.3 Out of Scope
- Options pricing or derivatives
- Futures contracts
- Forex (FX) markets
- Private equity / non-public assets
- High-frequency trading (< 1-minute intervals)
- Leveraged or short products

---

## 7. Stakeholder Map

| Stakeholder | Role | Interest |
|-------------|------|----------|
| Portfolio Manager | Primary consumer | Top/Bottom 5 recommendations + explanation |
| Quantitative Analyst | ML model consumer | Feature importance, model metrics |
| Data Engineer | Platform builder | Pipeline reliability, data quality |
| Risk Officer | Governance | Risk scores, model confidence |
| Executive Leadership | Business decision | Power BI dashboard summary |

---

## 8. Business Constraints

| Constraint | Value | Impact |
|-----------|-------|--------|
| Cloud Budget | Low (Community/Free tiers) | Databricks Community Edition; minimize Kinesis costs |
| Latency Tolerance | Minutes (not milliseconds) | WebSocket streaming → micro-batch, not tick-level HFT |
| Interpretability Requirement | High | SHAP values required for all model predictions |
| Data Privacy | Public data only | No proprietary data feeds |
| Operational Frequency | Weekly recommendations | Batch pipeline runs nightly; streaming for live updates only |

---

## 9. Definition of Done for This Phase

- [x] Prediction target formally defined and justified
- [x] Asset universe documented
- [x] Business problem articulated
- [x] Stakeholder map established
- [x] Analytical scope bounded
- [x] Business constraints documented

---

*Document Owner: Data Engineering Team*  
*Next Document: 02_data_source_document.md*
