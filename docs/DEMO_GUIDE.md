# MarketPulse Demonstration Guide for Project Lead

This guide provides a structured script to walk your team lead or stakeholders through all MarketPulse features and engineering layers in the local sandbox.

---

## Step 1: Execute Pipeline End-to-End (`demo_runner.py`)

Showcase pipeline execution:
1. Open a terminal/shell in the root directory.
2. Run:
   ```bash
   python demo_runner.py
   ```
3. Point out how the pipeline runs the following steps sequentially in a single automated process:
   - **Ingestion:** Downloads live Stock quotes (Alpaca API), Crypto trades (Alpaca API), Macro indicators (FRED API), and Financial news (NewsAPI).
   - **Medallion Architecture:** Standardises and validates ingestion data (Bronze -> Silver -> Gold).
   - **Feature Store & ML:** Pivots macro values, computes lexicon sentiment, aggregates technical indicators, trains 5 models (Linear, RF, XGBoost, LightGBM, PyTorch LSTM), and registers the best model.
   - **Backtester:** Runs historical backtest on out-of-sample data using the best model.
   - **Recommendation Engine:** Generates Top 5 buys/sells with confidence/risk metrics and explainability features.
   - **Data Warehouse Loader:** Inserts aggregated analytics tables into the local SQLite database.

---

## Step 2: Run Data Quality Checks (`data_quality.py`)

Demonstrate robust schema and type validation:
1. Run:
   ```bash
   python src/utils/data_quality.py
   ```
2. Point out that this implements 10+ Great Expectations style DQ metrics, checking for:
   - Null values in critical columns.
   - Strictly positive asset closing prices.
   - Valid high/low range limits.
   - Unique primary keys (no duplicate symbol/timestamp records).
   - Sentiment scores correctly normalized within [-1, 1].

---

## Step 3: Run Interactive BI Dashboard (`dashboard/app.py`)

Showcase the analytical interface:
1. Start the Streamlit app:
   ```bash
   streamlit run dashboard/app.py
   ```
2. Navigate through the 6 pages with your lead:
   - **Market Overview:** Review total monitored tickers, net daily sentiment, Heatmaps, and top movers.
   - **Technical Indicators:** Search any stock or crypto ticker to overlay Bollinger Bands, MACD, and RSI charts.
   - **ML Model Leaderboard:** Compare out-of-sample Sharpe and RMSE values across models.
   - **Strategy Backtester:** Contrast ML long-short strategy returns (CAGR: ~68%) against the benchmark index.
   - **Actionable Recommendations:** Display latest Buy/Sell signals alongside volatility risk classes and feature explanations.
   - **Data Quality Audit:** Verify status of all medallion layers.

---

## Step 4: Explore Model Metrics in MLflow UI

Showcase experiment tracking:
1. Start MLflow tracking server:
   ```bash
   mlflow ui --backend-store-uri sqlite:///mlruns.db
   ```
2. Open `http://localhost:5000` to show:
   - Metrics, parameters, and run files logged per model.
   - Registered models in the MLflow Model Registry.
