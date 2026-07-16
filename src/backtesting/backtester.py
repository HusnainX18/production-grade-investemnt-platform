"""
Phase 10 — Backtesting Framework.

Loads Gold feature table, performs inference on the out-of-sample Test set
using our registered Ridge Regression model (loaded from MLflow registry),
simulates a daily long-short portfolio rebalancing strategy with transaction costs,
compares it to a benchmark, computes key performance metrics (Sharpe, Sortino, MaxDD, CAGR),
saves the equity curve plot, and writes the results to AWS S3 Data Lake.
"""

import os
import sys
import warnings
from pathlib import Path
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore
    except Exception:
        pass

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from deltalake import DeltaTable
import mlflow
import mlflow.sklearn
from src.utils.s3_helper import write_gold_delta, get_s3_path, get_storage_options

load_dotenv()

# ─── Configuration ───────────────────────────────────────────────────────────

FEATURE_COLS = [
    "open", "high", "low", "close", "volume",
    "sma_20", "sma_50", "sma_200",
    "rsi_14", "macd", "macd_signal", "macd_hist",
    "bb_upper", "bb_lower", "bb_width",
    "return_1d", "return_5d", "return_20d",
    "volatility_20d",
    "rel_strength_sector",
    "volume_ratio",
    "price_position_52w",
    "vol_regime_ratio",
    "sentiment_pos", "sentiment_neg", "sentiment_neu", "sentiment_net",
]

TARGET_COL = "target_5d_return"
TRAIN_FRAC = 0.70
VAL_FRAC   = 0.15

# Trading constraints
STARTING_CAPITAL = 100000.0
TX_COST_BPS = 5.0 # 5 basis points (0.0005)
TOP_N = 5        # Number of long positions
BOTTOM_N = 5     # Number of short positions
REBALANCE_FREQ = 5  # Rebalance portfolio every N trading days (matches 5-day return target)


# ─── Load Model from Registry (with on-the-fly train fallback) ───────────────

def load_ensemble_models(X_train, y_train):
    """
    Load the tuned Ridge and XGBoost models from MLflow Registry.
    Falls back to on-the-fly training if registry is unavailable.
    Returns (ridge_model, xgb_model).
    """
    mlflow.set_tracking_uri("sqlite:///mlruns.db")

    def _load_or_fallback(name, load_fn, fallback_fn):
        try:
            from mlflow.tracking import MlflowClient
            client = MlflowClient()
            versions = client.get_latest_versions(name, stages=["None", "Staging", "Production"])
            latest_version = versions[0].version if versions else "1"
            print(f"    Loading '{name}:{latest_version}' from MLflow Registry...")
            m = load_fn(f"models:/{name}/{latest_version}")
            print(f"    Loaded '{name}' version {latest_version} from registry.")
            return m
        except Exception as e:
            print(f"   [WARNING] Could not load '{name}' ({e}). Training fallback...")
            m = fallback_fn()
            m.fit(X_train, y_train)
            return m

    from sklearn.linear_model import Ridge
    from xgboost import XGBRegressor

    ridge_model = _load_or_fallback(
        "investment-platform-ridge",
        mlflow.sklearn.load_model,
        lambda: Ridge(alpha=1.0),
    )
    xgb_model = _load_or_fallback(
        "investment-platform-xgboost",
        mlflow.xgboost.load_model,
        lambda: XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8,
                             random_state=42, verbosity=0),
    )
    return ridge_model, xgb_model


# ─── Main Backtesting Simulation ──────────────────────────────────────────────

def main():
    print("=" * 65)
    print(" PHASE 10 — TRADING PORTFOLIO BACKTESTING")
    print("=" * 65)

    # 1. Load Data
    gold_path = get_s3_path("features", layer="gold")
    storage_options = get_storage_options()
    print(f" Loading Gold features from {gold_path}...")
    dt = DeltaTable(gold_path, storage_options=storage_options)
    df = dt.to_pandas()
    
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)
    df_clean = df.dropna(subset=[TARGET_COL])
    
    # 2. Re-create splits to isolate out-of-sample Test set
    n = len(df_clean)
    n_train = int(n * TRAIN_FRAC)
    n_val   = int(n * VAL_FRAC)
    
    # Isolate raw data splits
    train_data = df_clean.iloc[:n_train]
    test_data = df_clean.iloc[n_train + n_val:].copy()
    
    available_features = [c for c in FEATURE_COLS if c in df_clean.columns]
    
    # Impute and Scale
    X_train_raw = train_data[available_features].ffill().fillna(0).values
    y_train = train_data[TARGET_COL].values
    
    X_test_raw = test_data[available_features].ffill().fillna(0).values
    
    # Scale features
    mean = X_train_raw.mean(axis=0)
    std  = X_train_raw.std(axis=0) + 1e-8
    X_test = (X_test_raw - mean) / std
    
    # 3. Load Models (ensemble)
    print("\n📦 Loading Ridge + XGBoost ensemble from MLflow Registry...")
    ridge_model, xgb_model = load_ensemble_models(X_train_raw, y_train)

    # 4. Generate predictions for Test Set (50/50 weighted ensemble)
    ridge_preds = ridge_model.predict(X_test)
    xgb_preds   = xgb_model.predict(X_test)
    test_data["predicted_return"] = 0.5 * ridge_preds + 0.5 * xgb_preds
    
    # 5. Run Day-by-Day Portfolio Rebalancer
    print("\n Simulating trading strategy over Test Set...")
    dates = sorted(test_data["date"].unique())
    portfolio_value = STARTING_CAPITAL
    equity_curve = []
    benchmark_curve = []
    
    # Track current holdings to compute rebalance volume for transaction costs
    current_allocations = {} # symbol -> weight
    
    benchmark_value = STARTING_CAPITAL
    
    for date in dates:
        day_data = test_data[test_data["date"] == date]
        if len(day_data) < (TOP_N + BOTTOM_N):
            # Not enough assets to trade on this day
            equity_curve.append(portfolio_value)
            benchmark_curve.append(benchmark_value)
            continue
            
        # Use the actual pre-computed 1-day return column for daily portfolio tracking
        day_data["daily_actual"] = day_data["return_1d"].fillna(0.0)
        
        # --- Benchmark: Equal Weighted Long-Only all assets ---
        benchmark_daily_return = day_data["daily_actual"].mean()
        benchmark_value *= (1.0 + benchmark_daily_return)
        benchmark_curve.append(benchmark_value)
        
        # --- Strategy: Long Top N, Short Bottom N (rebalance every REBALANCE_FREQ days) ---
        day_index = dates.index(date)
        is_rebalance_day = (day_index % REBALANCE_FREQ == 0)

        if is_rebalance_day:
            sorted_assets = day_data.sort_values("predicted_return")
            shorts = sorted_assets.head(BOTTOM_N)
            longs  = sorted_assets.tail(TOP_N)

            # Define target weights: Long positions, Short positions
            target_allocations = {}
            for sym in longs["symbol"]:
                target_allocations[sym] = 1.0 / TOP_N
            for sym in shorts["symbol"]:
                target_allocations[sym] = -1.0 / BOTTOM_N

            # Calculate rebalancing turnover to apply transaction costs
            turnover = 0.0
            all_symbols = set(target_allocations.keys()).union(current_allocations.keys())
            for sym in all_symbols:
                w_target  = target_allocations.get(sym, 0.0)
                w_current = current_allocations.get(sym, 0.0)
                turnover += abs(w_target - w_current)

            tx_costs = portfolio_value * turnover * (TX_COST_BPS / 10000.0)
            portfolio_value -= tx_costs
            current_allocations = target_allocations

        # Calculate today's performance using current_allocations
        strategy_return = 0.0
        sym_to_return = day_data.set_index("symbol")["daily_actual"].to_dict()
        for sym, weight in current_allocations.items():
            r = sym_to_return.get(sym, 0.0)
            strategy_return += weight * r

        portfolio_value *= (1.0 + strategy_return)
        equity_curve.append(portfolio_value)
        
    # 6. Performance Evaluation
    eq = np.array(equity_curve)
    bm = np.array(benchmark_curve)
    
    eq_returns = np.diff(eq) / eq[:-1]
    bm_returns = np.diff(bm) / bm[:-1]
    
    cagr = float((eq[-1] / STARTING_CAPITAL) ** (252 / len(dates)) - 1.0)
    bm_cagr = float((bm[-1] / STARTING_CAPITAL) ** (252 / len(dates)) - 1.0)
    
    # Sharpe Ratio
    std_dev = eq_returns.std()
    sharpe = float((eq_returns.mean() / (std_dev if std_dev > 0 else 1e-8)) * np.sqrt(252))
    
    # Sortino Ratio (Downside volatility)
    downside_returns = eq_returns[eq_returns < 0]
    downside_std = downside_returns.std() if len(downside_returns) > 0 else 1e-8
    sortino = float((eq_returns.mean() / downside_std) * np.sqrt(252))
    
    # Max Drawdown
    peaks = np.maximum.accumulate(eq)
    drawdowns = (eq - peaks) / peaks
    max_dd = float(drawdowns.min())
    
    # Win Rate
    win_rate = float(np.mean(eq_returns > 0))
    
    print("\n" + "=" * 65)
    print(" BACKTEST RESULTS SUMMARY")
    print("=" * 65)
    print(f" Starting Capital:  ${STARTING_CAPITAL:,.2f}")
    print(f" Final Port Value:  ${eq[-1]:,.2f}  (vs Benchmark: ${bm[-1]:,.2f})")
    print(f" CAGR:              {cagr:.2%}  (vs Benchmark: {bm_cagr:.2%})")
    print(f" Sharpe Ratio:       {sharpe:.3f}")
    print(f" Sortino Ratio:      {sortino:.3f}")
    print(f" Max Drawdown:       {max_dd:.2%}")
    print(f" Win Rate (Daily):   {win_rate:.2%}")
    print("=" * 65)
    
    # 7. Plot and Save Equity Curve
    print("\n Saving equity curve plot...")
    plt.figure(figsize=(12, 6))
    plt.plot(dates, eq, label="ML Long-Short Strategy (Top/Bottom 5)", color="#1f77b4", linewidth=2)
    plt.plot(dates, bm, label="Equal-Weighted Benchmark", color="#ff7f0e", linestyle="--", linewidth=2)
    plt.title("Out-of-Sample Portfolio Backtest (Phase 10)", fontsize=14, fontweight="bold")
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Portfolio Value ($)", fontsize=12)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(fontsize=11)
    
    # Save locally to docs directory
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    plot_path = docs_dir / "backtest_equity_curve.png"
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    print(f"    Saved plot locally to {plot_path}")
    
    # 8. Write Results back to Gold layer
    backtest_report_df = pd.DataFrame({
        "date": dates,
        "portfolio_value": eq,
        "benchmark_value": bm
    })
    
    # Convert date to string format for delta storage
    backtest_report_df["date"] = pd.Series(pd.to_datetime(backtest_report_df["date"])).dt.strftime("%Y-%m-%d")
    
    print(f"\n Materializing backtest results to Gold layer...")
    write_gold_delta(backtest_report_df, "backtest_report")
    print("    Backtest reports written successfully to S3/AWS!")
    
    # Log backtest results to MLflow
    try:
        mlflow.set_tracking_uri("sqlite:///mlruns.db")
        mlflow.set_experiment("investment-platform-phase9")
        with mlflow.start_run(run_name="BacktestRun"):
            mlflow.log_metrics({
                "backtest_cagr": cagr,
                "backtest_sharpe": sharpe,
                "backtest_sortino": sortino,
                "backtest_max_dd": max_dd, 
                "backtest_win_rate": win_rate
            })
            mlflow.log_artifact(str(plot_path), artifact_path="backtest_plots")
            print("    Logged backtest metrics and plots to MLflow!")
    except Exception as e:
        print(f"   [WARNING] Could not log backtest to MLflow ({e})")
        
    print("\n Phase 10 — Backtesting completed successfully!")


if __name__ == "__main__":
    main()
