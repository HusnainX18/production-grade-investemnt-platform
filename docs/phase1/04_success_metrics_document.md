# Success Metrics Document
## Intelligent Investment Recommendation Platform

**Project:** Intelligent Investment Recommendation Platform  
**Phase:** 1 — Research & System Design  
**Document Type:** Success Metrics  
**Version:** 1.0  
**Date:** June 2026  

---

## 1. Purpose of This Document

A project without measurable success criteria is not an engineering project — it is an experiment with no stopping condition. This document defines every metric used to evaluate success across five distinct layers of the platform:

| Layer | What We Measure | Why It Matters |
|-------|----------------|----------------|
| **Data Quality** | Accuracy and completeness of raw/clean data | Garbage in = garbage predictions |
| **Pipeline Health** | Reliability of batch and streaming pipelines | Broken pipes = no data = platform failure |
| **ML Model Performance** | Predictive accuracy of trained models | Model quality determines recommendation quality |
| **Portfolio / Backtesting** | Financial performance of the strategy | Business outcome — does it make money? |
| **Ranking Quality** | Accuracy of Top 5 / Bottom 5 selections | Core business deliverable |

---

## 2. Data Quality Metrics

### 2.1 Why Data Quality Metrics Come First

Every other metric is meaningless if the underlying data is wrong. A model that achieves 70% directional accuracy on clean data will achieve 50% on corrupted data. The first question after any pipeline run should always be: **"Is the data I'm about to use trustworthy?"**

### 2.2 Completeness Metrics

**Definition:** What percentage of expected data actually arrived and was stored?

| Metric | Formula | Target | Threshold | Measurement Frequency |
|--------|---------|--------|-----------|----------------------|
| **Stock Completeness Rate** | (rows received / expected rows) × 100 | ≥ 99.5% | < 97% = ALERT | Daily |
| **Crypto Completeness Rate** | (coins received / 10 coins) × 100 | 100% | < 90% = ALERT | Daily |
| **Macro Series Coverage** | (series updated / 10 series) × 100 | ≥ 95% | < 80% = ALERT | Daily |
| **News Article Volume** | Count of articles ingested per day | ≥ 200/day | < 50/day = ALERT | Daily |
| **Trading Day Coverage** | (actual trading days / expected days) × 100 | 100% | < 98% = ALERT | Monthly |

**Expected rows example for Stock:**
```
50 tickers × 252 trading days = 12,600 rows per year expected
Daily: 50 tickers = 50 rows (for the most recent day)
```

### 2.3 Validity Metrics

**Definition:** Of the data that arrived, what percentage is logically valid?

| Metric | Check | Target | Measurement |
|--------|-------|--------|-------------|
| **Price Validity Rate** | close > 0 AND high ≥ close ≥ low AND low > 0 | ≥ 99.9% | Per Bronze load |
| **Volume Validity Rate** | volume ≥ 0 | ≥ 99.9% | Per Bronze load |
| **Timestamp Validity** | date is a valid trading day (market calendar) | ≥ 99.9% | Per Bronze load |
| **OHLC Consistency** | high ≥ open AND high ≥ close AND low ≤ open AND low ≤ close | ≥ 99.9% | Per Bronze load |
| **Macro Value Range** | value within historically plausible range per series | ≥ 99.9% | Per Bronze load |

**OHLC consistency explanation:**
```
A valid bar MUST satisfy:
  High ≥ Open   (high can't be below where we opened)
  High ≥ Close  (high can't be below where we closed)
  Low ≤ Open    (low can't be above where we opened)
  Low ≤ Close   (low can't be above where we closed)

Violation = data corruption or API parsing error
```

### 2.4 Duplication Metrics

| Metric | Formula | Target | Impact of Failure |
|--------|---------|--------|------------------|
| **Duplicate Rate (Stock)** | (duplicate rows / total rows) × 100 | < 0.1% | Double-counted volume; inflated features |
| **Duplicate Rate (News)** | (duplicate article IDs / total articles) × 100 | < 1% | Sentiment bias toward repeated stories |
| **Idempotency Test** | Run ingestion twice; row count delta | = 0 | Verifies MERGE/UPSERT logic works correctly |

### 2.5 Freshness Metrics

**Definition:** How recent is the most recent data in the platform?

| Metric | Formula | Target | Alert Threshold |
|--------|---------|--------|----------------|
| **Stock Data Lag** | now() - max(date) in silver_stock | ≤ 1 trading day | > 2 days = CRITICAL |
| **Macro Data Lag** | For daily series: now() - max(obs_date) | ≤ 2 business days | > 5 days = ALERT |
| **Streaming Latency (p50)** | median(processing_ts - event_timestamp) | ≤ 90 seconds | > 5 minutes = ALERT |
| **Streaming Latency (p95)** | 95th percentile latency | ≤ 3 minutes | > 10 minutes = CRITICAL |

### 2.6 Data Quality Scorecard

This scorecard is generated automatically after each pipeline run and stored in `gold/quality_scorecard`:

```
DATA QUALITY SCORECARD — Example Output
════════════════════════════════════════════════════════════════════════════

Report Date: 2024-06-10   Pipeline Run: daily_batch_20240610

┌──────────────────────────────┬──────────────────┬──────────┬──────────┐
│  Metric                      │  Value           │  Target  │  Status  │
├──────────────────────────────┼──────────────────┼──────────┼──────────┤
│  Stock Completeness Rate     │  100.0%          │  ≥99.5%  │  ✅ PASS │
│  Crypto Completeness Rate    │  100.0%          │  100%    │  ✅ PASS │
│  Macro Series Coverage       │  90.0%           │  ≥95%    │  ⚠️ WARN │
│  News Article Volume         │  347 articles    │  ≥200    │  ✅ PASS │
│  Price Validity Rate         │  99.98%          │  ≥99.9%  │  ✅ PASS │
│  Volume Validity Rate        │  100.0%          │  ≥99.9%  │  ✅ PASS │
│  OHLC Consistency Rate       │  99.96%          │  ≥99.9%  │  ✅ PASS │
│  Stock Duplicate Rate        │  0.0%            │  <0.1%   │  ✅ PASS │
│  Stock Data Lag              │  0 days          │  ≤1 day  │  ✅ PASS │
│  Streaming Latency (p95)     │  87 seconds      │  ≤180s   │  ✅ PASS │
├──────────────────────────────┼──────────────────┼──────────┼──────────┤
│  OVERALL QUALITY SCORE       │  9/10 metrics    │  All     │  ✅ 90%  │
└──────────────────────────────┴──────────────────┴──────────┴──────────┘

Warning Detail: MACRO_SERIES_COVERAGE — GDP series not yet released for Q2
Action: No action required. GDP is a quarterly release. Expected release: Aug 2024.
```

---

## 3. Pipeline Health Metrics

### 3.1 Why Pipeline Health Must Be Measured Separately from Data Quality

A pipeline can succeed (data is present and valid) while being slow, unreliable, or expensive. These operational metrics protect against silent degradation.

### 3.2 Batch Pipeline Metrics

| Metric | Definition | Target | Critical Threshold |
|--------|-----------|--------|-------------------|
| **Pipeline Success Rate** | % of scheduled runs that complete without error | ≥ 99% weekly | < 90% in a week |
| **Pipeline Duration — Stock** | Wall clock time for full stock ingestion | ≤ 10 minutes | > 20 minutes |
| **Pipeline Duration — Silver ETL** | Wall clock time for Silver transformation | ≤ 20 minutes | > 45 minutes |
| **Pipeline Duration — Feature Eng** | Wall clock time for Gold feature engineering | ≤ 30 minutes | > 60 minutes |
| **End-to-End Batch Latency** | Time from market close to Gold layer ready | ≤ 2 hours | > 4 hours |
| **Retry Rate** | % of tasks that required retry before success | < 5% | > 20% |
| **Cost per Run** | Estimated Databricks DBU cost per pipeline run | < $0.50/run | > $2.00/run |

### 3.3 Streaming Pipeline Metrics

| Metric | Definition | Target | Critical Threshold |
|--------|-----------|--------|-------------------|
| **Records Processed per Minute** | Throughput of Kinesis consumer | ≥ 100 records/min (market hours) | < 10 records/min = possible outage |
| **Consumer Lag** | Records in Kinesis shard not yet processed | < 1,000 records | > 10,000 = falling behind |
| **Processing Latency p50** | Median event-to-table latency | ≤ 60 seconds | > 5 minutes |
| **Processing Latency p95** | 95th percentile latency | ≤ 3 minutes | > 10 minutes |
| **Streaming Job Uptime** | % of market hours when job is running | ≥ 99% | < 95% |
| **Kinesis PUT Errors** | Failed PutRecord calls from Producer | < 0.1% | > 1% |
| **Checkpoint Frequency** | How often consumer commits offset | Every 30 seconds | > 5 minutes = risk of reprocessing |

### 3.4 Monitoring Dashboard Metrics (CloudWatch)

All of the above are published as CloudWatch custom metrics and displayed on the monitoring dashboard:

```
CloudWatch Namespace: InvestmentPlatform/Pipeline
Metrics published every 5 minutes:

├── BatchPipeline/
│   ├── StockIngestionDurationSeconds
│   ├── SilverETLDurationSeconds
│   ├── FeatureEngDurationSeconds
│   ├── PipelineSuccessCount
│   └── PipelineFailureCount
│
└── StreamingPipeline/
    ├── RecordsProcessedPerMinute
    ├── ConsumerLagCount
    ├── LatencyP50Seconds
    ├── LatencyP95Seconds
    ├── KinesisErrorCount
    └── StreamingJobUptime
```

---

## 4. Machine Learning Model Performance Metrics

### 4.1 Why Finance ML Needs Different Metrics Than Standard ML

Standard ML practitioners optimize for accuracy or F1-score. Financial ML practitioners know these are wrong objectives. The reason:

- A model with 60% accuracy on predicting stock direction is worthless if the 40% it gets wrong are the large moves
- A model with 48% accuracy that correctly identifies the top 20% of performers is profitable

This is why the financial ML community uses **rank-based metrics** (IC, NDCG) rather than magnitude-error metrics (RMSE, MAE) as the primary evaluation.

### 4.2 Regression Metrics (Primary Target: forward_return_5d)

| Metric | Formula | Good Value | Interpretation |
|--------|---------|------------|----------------|
| **RMSE** | √(mean((ŷ−y)²)) | < 2.0% | Average prediction error in return % units |
| **MAE** | mean(\|ŷ−y\|) | < 1.5% | Median prediction error in return % units |
| **MAPE** | mean(\|ŷ−y\|/\|y\|) × 100 | < 50% | Relative error (less useful for near-zero returns) |
| **R²** | 1 − SS_res/SS_tot | > 0.03 in finance | % of variance explained — even 3% is meaningful |

**R² Context for Finance:**

Unlike most ML domains where R² > 0.9 is expected, in financial return prediction:
```
R² < 0.01  → Model has no useful signal (likely worse than noise)
R² = 0.02  → Marginal signal; usable with caution
R² = 0.05  → Good for finance; publishable in quant research
R² = 0.10  → Excellent; professional quant fund territory
R² > 0.15  → Likely overfit or look-ahead bias — investigate immediately
```

### 4.3 Ranking Metrics (Business-Critical)

These metrics evaluate whether the model correctly identifies top and bottom performers — the direct input to the recommendation engine.

#### Information Coefficient (IC)

**Definition:** Spearman rank correlation between predicted returns and actual returns across all assets for a given period.

**Formula:**
```
IC = Spearman_ρ(predicted_ranks, actual_ranks)

Range: -1.0 (perfect inverse ranking) to +1.0 (perfect ranking)
```

**Interpretation table:**

| IC Value | Meaning | Practical Assessment |
|----------|---------|---------------------|
| IC < 0.0 | Model ranks worse than random | Model is harmful — do not deploy |
| IC = 0.0 | Model has no ranking ability | Equivalent to random selection |
| IC = 0.02–0.05 | Weak but positive signal | Marginal; usable in a diversified ensemble |
| IC = 0.05–0.10 | **Moderate signal** | **Target range for this project** |
| IC = 0.10–0.15 | Strong signal | Excellent quant research result |
| IC > 0.15 | Very strong signal | Investigate for look-ahead bias first |

**IC Stability (ICIR — Information Coefficient Information Ratio):**
```
ICIR = mean(IC) / std(IC)

Interpretation:
ICIR > 0.5 → IC is stable across periods (reliable signal)
ICIR < 0.3 → IC is highly variable (unreliable signal, even if mean IC is positive)
```

#### Directional Accuracy

**Definition:** Percentage of predictions where the sign of the predicted return matches the sign of the actual return.

```
Directional_Accuracy = (correct sign predictions / total predictions) × 100

Baseline (random): 50%
Target: ≥ 55%
Excellent: ≥ 60%
```

**Why 55% is meaningful:**
In financial markets, 55% directional accuracy, applied consistently over hundreds of trades with appropriate position sizing, produces a statistically significant edge. A Sharpe ratio of ~0.8–1.2 can be achieved with just 55% directional accuracy and disciplined risk management.

#### Top-K Precision

**Definition:** Of the assets predicted to be in the Top K performers, what fraction actually are in the Top K?

```
Precision@K = (assets correctly in Top K) / K

For K=5 (Top 5 recommendations):
Target: ≥ 60% (3 of 5 are genuinely top performers)
Excellent: ≥ 80% (4 of 5)
```

### 4.4 Model Comparison Framework

All models are evaluated on the same time-series train/validation/test split:

```
TIME-SERIES SPLIT (NO RANDOM SHUFFLING)
═════════════════════════════════════════

Jan 2020 ─────────────────────────── Dec 2022 ─── Jun 2023 ─── Dec 2023
│                                              │             │           │
│                TRAIN SET                    │  VALIDATION │   TEST    │
│            (~750 trading days)               │  (~126 days)│  (~126d)  │
└──────────────────────────────────────────────┴─────────────┴───────────┘

Walk-Forward Validation (for final model selection):
Window 1: Train Jan2020–Dec2021, Test 2022 Q1
Window 2: Train Jan2020–Jun2022, Test 2022 Q3
Window 3: Train Jan2020–Dec2022, Test 2023 Q1
Window 4: Train Jan2020–Jun2023, Test 2023 Q3
Average metrics across all windows = final model score
```

**Model Comparison Table (target output from Phase 8):**

```
MODEL COMPARISON REPORT (Phase 8 Output Template)
════════════════════════════════════════════════════════════════════════════════════

Model               │ RMSE  │ MAE   │  R²   │  IC   │ Dir.Acc │ Prec@5 │ Train(s)
────────────────────┼───────┼───────┼───────┼───────┼─────────┼────────┼──────────
Linear Regression   │ 2.34% │ 1.78% │ 0.012 │ 0.041 │  52.1%  │  40.0% │   < 1s
Random Forest       │ 2.18% │ 1.65% │ 0.028 │ 0.063 │  54.3%  │  60.0% │    45s
XGBoost (Primary)   │ 2.09% │ 1.58% │ 0.041 │ 0.078 │  55.7%  │  60.0% │    12s
LightGBM            │ 2.11% │ 1.60% │ 0.038 │ 0.074 │  55.2%  │  60.0% │     4s
LSTM                │ 2.41% │ 1.84% │ 0.008 │ 0.031 │  51.4%  │  40.0% │   180s
────────────────────┴───────┴───────┴───────┴───────┴─────────┴────────┴──────────
✅ Winner: XGBoost  (best IC, best Precision@5, fast training)
```

> **Note:** The values above are illustrative. Actual values will be populated in Phase 8.

### 4.5 Model Monitoring Metrics (Production)

Once deployed, the model's performance is monitored on an ongoing basis:

| Metric | Definition | Alert Threshold | Action |
|--------|-----------|----------------|--------|
| **IC 4-Week Rolling** | Rolling 4-week average IC | IC < 0.02 for 2 consecutive weeks | Trigger model retraining |
| **Prediction Distribution Drift** | KS-test on predicted return distribution vs training | p-value < 0.05 | Investigate data drift |
| **Feature Drift Score** | PSI (Population Stability Index) for top 10 features | PSI > 0.25 for any feature | Retraining required |
| **Directional Accuracy (Rolling)** | 4-week rolling directional accuracy | < 50% for 2 weeks | Emergency retrain |

**PSI (Population Stability Index) Interpretation:**
```
PSI < 0.10  → No significant drift (safe to use model)
PSI = 0.10–0.25  → Minor drift (monitor closely, consider retraining)
PSI > 0.25  → Major drift (retrain immediately)
```

---

## 5. Portfolio & Backtesting Metrics

### 5.1 Backtesting Strategy Definition

The strategy being backtested:

```
STRATEGY SPECIFICATION
═══════════════════════
Name: ML Weekly Rotation Strategy
Universe: 60 assets (50 equities + 10 crypto)
Rebalancing: Every Monday at market open
Position sizing: Equal weight
Long positions: Top 5 predicted assets (20% each = 100% long)
Short positions: None (long-only for simplicity)
Transaction cost: 0.1% per trade (per leg)
Slippage: 0.05% per trade
Benchmark 1: S&P 500 (SPY ETF)
Benchmark 2: Nasdaq (QQQ ETF)
Backtest period: Jan 2020 – Dec 2024
```

### 5.2 Return Metrics

| Metric | Formula | Target | Minimum Acceptable |
|--------|---------|--------|--------------------|
| **Total Return** | (End_Value − Start_Value) / Start_Value × 100 | > SPY total return | > 0% (positive) |
| **Annualized Return (CAGR)** | (1 + Total Return)^(1/years) − 1 | > 15% | > S&P 500 (~11% avg) |
| **Annualized Volatility** | std(weekly returns) × √52 | < 25% | < 40% |
| **Best Week** | max(weekly returns) | N/A (informational) | — |
| **Worst Week** | min(weekly returns) | > −15% | > −25% |

### 5.3 Risk-Adjusted Return Metrics

#### Sharpe Ratio

**Definition:** Return earned per unit of risk taken.

```
Sharpe Ratio = (Portfolio Annual Return − Risk Free Rate) / Portfolio Annual Volatility

Risk-Free Rate: 5% (current approximate T-bill rate)

Example:
  Portfolio return: 18%, Volatility: 14%
  Sharpe = (18% − 5%) / 14% = 0.93
```

**Interpretation:**

| Sharpe Ratio | Assessment | Context |
|-------------|-----------|---------|
| < 0.0 | Negative | Strategy loses money risk-adjusted |
| 0.0 – 0.5 | Poor | Worse than holding cash or bonds |
| 0.5 – 1.0 | Acceptable | Better than market benchmark but with caveats |
| **1.0 – 2.0** | **Good** | **Target range for this project** |
| 2.0 – 3.0 | Excellent | Professional quant fund performance |
| > 3.0 | Exceptional | Suspect look-ahead bias or market anomaly |

#### Sortino Ratio

**Definition:** Like Sharpe, but only penalizes downside volatility (losses), not upside volatility (gains).

```
Sortino Ratio = (Portfolio Return − Risk Free Rate) / Downside Deviation

Downside Deviation = std(weekly returns where return < 0) × √52

Target: Sortino > 1.5
Why: Investors don't mind upside volatility; Sortino penalizes only harmful volatility
```

#### Maximum Drawdown (MDD)

**Definition:** Largest peak-to-trough decline in portfolio value.

```
MDD = (Peak_Value − Trough_Value) / Peak_Value × 100

Example:
  Portfolio peaks at $1,000,000 in Feb 2021
  Portfolio drops to $720,000 by Jun 2022
  MDD = (1,000,000 − 720,000) / 1,000,000 = 28%

Target: MDD < 25%
This means: the strategy never loses more than 25% from its previous peak
```

| MDD Value | Investor Acceptability |
|-----------|----------------------|
| < 10% | Highly conservative; pension fund acceptable |
| 10–20% | Conservative to moderate |
| **20–30%** | **Moderate; acceptable for this strategy** |
| 30–50% | Aggressive; retail investor tolerance limit |
| > 50% | Unacceptable; strategy would be abandoned by most investors |

#### Calmar Ratio

**Definition:** Annual return divided by Maximum Drawdown. Answers: "How much return do I get per unit of worst loss?"

```
Calmar Ratio = Annualized Return / |Maximum Drawdown|

Target: Calmar > 0.8
```

#### Win Rate

**Definition:** Percentage of weeks where the strategy produced a positive return.

```
Win Rate = (profitable weeks / total weeks) × 100

Context:
  A strategy can be profitable overall with a win rate of only 45% IF the average
  winning week is much larger than the average losing week.
  
  Win Rate × Avg Gain > (1 − Win Rate) × Avg Loss = Positive Expectancy
  
Target: Win Rate > 55%
```

### 5.4 Benchmark Comparison Framework

| Metric | ML Strategy | SPY (S&P 500) | QQQ (Nasdaq) | Assessment |
|--------|------------|---------------|--------------|------------|
| Total Return (5yr) | *Phase 9 output* | ~150% | ~190% | Must beat SPY |
| Annualized Return | *Phase 9 output* | ~11% | ~14% | Must beat SPY |
| Annual Volatility | *Phase 9 output* | ~18% | ~22% | Prefer ≤ SPY |
| Sharpe Ratio | *Phase 9 output* | ~0.5 | ~0.55 | Must beat 0.8 |
| Max Drawdown | *Phase 9 output* | ~−34% | ~−35% | Must be better |
| Win Rate | *Phase 9 output* | ~57% | ~55% | Target ≥ 55% |

> **Note:** SPY and QQQ values are approximate 5-year historical averages. Exact values will be computed during Phase 9.

### 5.5 Regime Analysis

Performance must be evaluated separately across market regimes:

| Period | Market Regime | Expected Strategy Behavior |
|--------|--------------|---------------------------|
| Jan 2020 – Feb 2020 | Bull market | Should outperform — strong trend signals |
| Mar 2020 | COVID crash | May underperform — regime break; signals invalid |
| Apr 2020 – Dec 2021 | Strong bull | Should outperform — clear momentum signals |
| Jan 2022 – Dec 2022 | Bear market | May underperform — tests strategy defensiveness |
| Jan 2023 – Dec 2024 | Recovery/bull | Should outperform — recovery signals strong |

**Success criterion for regime analysis:** Strategy must not lose more than 1.5× the benchmark in any single regime.

---

## 6. Ranking Quality Metrics

### 6.1 Why Ranking Quality Is the Primary Business Metric

The business deliverable is: **Top 5 assets to buy, Bottom 5 assets to avoid.** The executive does not care about RMSE. They care about one question: *"If I followed your Top 5 recommendations each week for a year, would I have made money?"*

### 6.2 Top-5 Hit Rate

**Definition:** Percentage of weekly predictions where at least 3 of the Top 5 predicted assets finish in the actual top quintile (top 20% of all asset returns) for that week.

```
Top-5 Hit Rate = (weeks where ≥3/5 predicted top performers are in actual top quintile)
                 ─────────────────────────────────────────────────────────────────────
                                      total weeks evaluated

Target: ≥ 60%
Interpretation: In 6 out of 10 weeks, the Top 5 list contains ≥ 3 genuine top performers
```

### 6.3 Bottom-5 Hit Rate

Same calculation for Bottom 5 predicted assets vs. actual bottom quintile performers.

```
Target: ≥ 60%
```

### 6.4 NDCG (Normalized Discounted Cumulative Gain)

**Definition:** A ranking quality metric borrowed from information retrieval. Rewards the model for correctly placing the highest returns at the top of the ranking, with diminishing credit for correct placements further down the list.

```
DCG@K = Σ(i=1 to K) [actual_return_i / log2(i + 1)]

NDCG@K = DCG@K / IDCG@K
where IDCG@K = DCG of a perfect ranking

Range: 0 (worst) to 1.0 (perfect ranking)
Target: NDCG@5 ≥ 0.65
```

**Intuition:** If the #1 predicted asset (highest confidence) turns out to be the actual worst performer, NDCG penalizes this heavily. It rewards placing the right assets at the top of the list — not just somewhere in the Top 5.

### 6.5 Weekly Ranking Summary Report (Output Format)

```
WEEKLY RANKING REPORT — Example Output
═══════════════════════════════════════════════════════════════════════════════════

Week of: 2024-06-10 to 2024-06-14   Model Version: xgboost_v3.2

TOP 5 RECOMMENDATIONS (BUY)
┌────┬────────┬──────────────┬────────────────────┬────────────┬────────────────────────────┐
│Rank│ Ticker │ Pred. Return │ Confidence Score   │ Risk Score │ Key Drivers (SHAP Top 3)   │
├────┼────────┼──────────────┼────────────────────┼────────────┼────────────────────────────┤
│  1 │ NVDA   │   +3.82%     │ HIGH (0.87)        │ MEDIUM     │ RSI_oversold, Earn_beat,   │
│    │        │              │                    │            │ Macro_rate_stable          │
├────┼────────┼──────────────┼────────────────────┼────────────┼────────────────────────────┤
│  2 │ BTC-USD│   +3.24%     │ HIGH (0.81)        │ HIGH       │ Sentiment_pos, Vol_spike,  │
│    │        │              │                    │            │ Dominance_high             │
├────┼────────┼──────────────┼────────────────────┼────────────┼────────────────────────────┤
│  3 │ META   │   +2.91%     │ MEDIUM (0.74)      │ LOW        │ MACD_cross, News_positive, │
│    │        │              │                    │            │ P/E_below_avg              │
├────┼────────┼──────────────┼────────────────────┼────────────┼────────────────────────────┤
│  4 │ AMD    │   +2.67%     │ MEDIUM (0.71)      │ MEDIUM     │ Momentum_strong, Sector_   │
│    │        │              │                    │            │ tailwind, Vol_decreasing   │
├────┼────────┼──────────────┼────────────────────┼────────────┼────────────────────────────┤
│  5 │ JPM    │   +1.94%     │ MEDIUM (0.68)      │ LOW        │ Rate_curve_positive, Earn_ │
│    │        │              │                    │            │ beat, RSI_normal           │
└────┴────────┴──────────────┴────────────────────┴────────────┴────────────────────────────┘

BOTTOM 5 RECOMMENDATIONS (AVOID / SHORT)
┌────┬────────┬──────────────┬────────────────────┬────────────┬────────────────────────────┐
│Rank│ Ticker │ Pred. Return │ Confidence Score   │ Risk Score │ Key Drivers (SHAP Top 3)   │
├────┼────────┼──────────────┼────────────────────┼────────────┼────────────────────────────┤
│  1 │ INTC   │   -2.41%     │ HIGH (0.83)        │ HIGH       │ Earnings_miss, Market_     │
│    │        │              │                    │            │ share_loss, RSI_high       │
├────┼────────┼──────────────┼────────────────────┼────────────┼────────────────────────────┤
│  2 │ XRP-USD│   -2.18%     │ MEDIUM (0.71)      │ VERY HIGH  │ Regulatory_risk, Sent_neg, │
│    │        │              │                    │            │ Vol_spike_down             │
└────┴────────┴──────────────┴────────────────────┴────────────┴────────────────────────────┘

RANKING QUALITY (This Week):
  IC (Spearman correlation): 0.082        ✅
  Top-5 Hit Rate: 4/5 (80%)              ✅
  Bottom-5 Hit Rate: 2/2 (100%)          ✅
  NDCG@5: 0.71                           ✅
```

---

## 7. Complete Success Criteria Summary

The platform is considered **successful** when ALL of the following thresholds are met:

### Must-Have (Required for Go/No-Go Decision)

| # | Category | Metric | Required Threshold |
|---|----------|--------|-------------------|
| 1 | Data Quality | Stock Completeness Rate | ≥ 99.5% |
| 2 | Data Quality | Price Validity Rate | ≥ 99.9% |
| 3 | Pipeline Health | Batch Pipeline Success Rate | ≥ 99% (weekly) |
| 4 | Pipeline Health | Streaming Uptime | ≥ 99% (market hours) |
| 5 | ML Performance | IC (Primary Model) | ≥ 0.05 |
| 6 | ML Performance | Directional Accuracy | ≥ 55% |
| 7 | ML Performance | Beat Linear Regression Baseline | IC must be > baseline IC |
| 8 | Backtesting | Sharpe Ratio | ≥ 0.8 |
| 9 | Backtesting | Beat SPY Total Return | Strategy > SPY |
| 10 | Backtesting | Max Drawdown | ≤ 30% |
| 11 | Ranking | Top-5 Weekly Hit Rate | ≥ 60% |
| 12 | Ranking | Bottom-5 Weekly Hit Rate | ≥ 60% |

### Should-Have (Target for Excellence)

| # | Category | Metric | Target |
|---|----------|--------|--------|
| 1 | ML Performance | IC | ≥ 0.08 |
| 2 | ML Performance | RMSE | ≤ 2.0% |
| 3 | Backtesting | Sharpe Ratio | ≥ 1.2 |
| 4 | Backtesting | Annualized Return | ≥ 15% |
| 5 | Backtesting | Win Rate | ≥ 55% |
| 6 | Ranking | NDCG@5 | ≥ 0.65 |
| 7 | Ranking | Top-5 Hit Rate | ≥ 70% |
| 8 | Cost | Monthly AWS + Databricks cost | ≤ $50/month |

---

## 8. Metrics Implementation Plan

| Metric Category | Tool | Output Location | Frequency |
|----------------|------|-----------------|-----------|
| Data Quality | Python Great Expectations / custom Spark assertions | `gold/quality_scorecard` Delta table | Per pipeline run |
| Pipeline Health | AWS CloudWatch custom metrics | CloudWatch Dashboard | Every 5 minutes |
| ML Performance | MLflow experiment tracking | MLflow UI + `gold/ml_metrics` | Per training run |
| Backtesting | Python (vectorbt / custom) | `gold/backtesting_report` Delta table | Per backtest run |
| Ranking Quality | Custom Python scoring | `gold/recommendations` Delta table | Weekly |
| Power BI Display | All above → Databricks SQL | Power BI ML Dashboard | Daily refresh |

---

*Document Owner: Data Engineering Team & ML Architecture Team*  
*Phase 1 Complete. Next: Phase 2 — Data Platform Foundation*
