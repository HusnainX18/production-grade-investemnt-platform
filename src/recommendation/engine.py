"""
Phase 11 — Recommendation Engine.

Loads the Gold feature table, extracts the most recent date, runs inference
using our best registered model, scores and ranks assets to select Top 5 Buy
and Bottom 5 Sell/Short opportunities. Computes confidence and risk scores,
calculates feature-contribution explainability, saves a markdown report,
and writes recommendations to AWS S3 Data Lake Gold layer.
"""

import os
import sys
import warnings
from pathlib import Path

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
    "sentiment_pos", "sentiment_neg", "sentiment_neu", "sentiment_net",
]

TARGET_COL = "target_5d_return"
TRAIN_FRAC = 0.70
VAL_FRAC   = 0.15


# ─── Helper Utilities ─────────────────────────────────────────────────────────

def load_best_model(df_clean, feat_names) -> tuple:
    """Load Ridge model from MLflow registry or retrain if registry fails."""
    mlflow.set_tracking_uri("sqlite:///mlruns.db")
    model_name = "investment-platform-best-model"
    
    # Train set features (needed for scaler reference & fallback)
    n = len(df_clean)
    n_train = int(n * TRAIN_FRAC)
    train_data = df_clean.iloc[:n_train]
    X_train_raw = train_data[feat_names].ffill().fillna(0).values
    y_train = train_data[TARGET_COL].values
    
    mean = X_train_raw.mean(axis=0)
    std  = X_train_raw.std(axis=0) + 1e-8
    
    try:
        print(f" Attempting to load model '{model_name}:1' from MLflow Registry...")
        model = mlflow.sklearn.load_model(f"models:/{model_name}/1")
        print("    Model loaded successfully from registry!")
        return model, mean, std
    except Exception as e:
        print(f"   [WARNING] Could not load from Model Registry ({e}). Retraining on-the-fly...")
        from sklearn.linear_model import Ridge
        model = Ridge(alpha=1.0)
        model.fit((X_train_raw - mean) / std, y_train)
        print("    Ridge model retrained successfully!")
        return model, mean, std


def get_risk_label(volatility: float) -> str:
    """Convert raw 20-day price volatility to a discrete risk category."""
    if volatility < 0.015:
        return "Low"
    elif volatility < 0.035:
        return "Medium"
    else:
        return "High"


def get_confidence_score(predicted_return: float, max_pred: float) -> float:
    """Determine confidence score (0 to 100) based on prediction magnitude relative to maximums."""
    if max_pred <= 0:
        return 50.0
    score = (abs(predicted_return) / max_pred) * 100.0
    return float(np.clip(score, 10.0, 99.0))


# ─── Main Recommendation Generator ───────────────────────────────────────────

def main():
    print("=" * 65)
    print(" PHASE 11 — INVESTMENT RECOMMENDATION ENGINE")
    print("=" * 65)

    # 1. Load Data
    gold_path = get_s3_path("features", layer="gold")
    storage_options = get_storage_options()
    print(f" Loading Gold features from {gold_path}...")
    dt = DeltaTable(gold_path, storage_options=storage_options)
    df = dt.to_pandas()
    
    df["date"] = pd.to_datetime(df["date"])
    df_clean = df.dropna(subset=[TARGET_COL])
    
    # Identify latest date
    latest_date = df["date"].max()
    latest_date_str = latest_date.strftime("%Y-%m-%d")
    print(f"📅 Most recent date identified in dataset: {latest_date_str}")
    
    # Filter features for this date
    latest_df = df[df["date"] == latest_date].copy().reset_index(drop=True)
    if latest_df.empty:
        print("   [ERROR] No active assets found on the latest date. Exiting.")
        sys.exit(1)
    print(f"   Found {len(latest_df)} active assets.")
    
    available_features = [c for c in FEATURE_COLS if c in df.columns]
    
    # 2. Load Model & Scale Parameters
    model, mean, std = load_best_model(df_clean, available_features)
    
    # Extract model coefficients for explainability
    try:
        coefs = model.coef_
    except AttributeError:
        # Fallback to dummy coefficients if model structure differs
        coefs = np.zeros(len(available_features))
        
    # 3. Preprocess and Predict on latest data
    X_latest_raw = latest_df[available_features].ffill().fillna(0).values
    X_latest = (X_latest_raw - mean) / std
    
    latest_df["predicted_return"] = model.predict(X_latest)
    
    # 4. Compute Risk & Confidence Scores
    max_pred = float(latest_df["predicted_return"].abs().max())
    
    recs = []
    for idx, row in latest_df.iterrows():
        # Volatility is already in decimal, e.g. 0.02
        vol = float(row.get("volatility_20d", 0.0))
        risk = get_risk_label(vol)
        
        pred_ret = float(row["predicted_return"])
        conf = get_confidence_score(pred_ret, max_pred)
        
        # Calculate feature contributions (explainability)
        scaled_feat_vals = X_latest[idx]
        contributions = scaled_feat_vals * coefs
        
        # Map back to feature names
        cont_map = list(zip(available_features, contributions))
        
        # Sort by impact magnitude
        cont_map_sorted = sorted(cont_map, key=lambda x: x[1])
        
        top_positive = [f"{feat} (+{val:.4f})" for feat, val in reversed(cont_map_sorted) if val > 0][:2]
        top_negative = [f"{feat} ({val:.4f})" for feat, val in cont_map_sorted if val < 0][:2]
        
        explainability = f"Pos: {', '.join(top_positive)} | Neg: {', '.join(top_negative)}"
        
        recs.append({
            "symbol": row["symbol"],
            "predicted_5d_return": pred_ret,
            "confidence_score": conf,
            "risk_score": risk,
            "explainability": explainability,
            "volatility_20d": vol
        })
        
    recs_df = pd.DataFrame(recs)
    
    # 5. Extract Top 5 and Bottom 5 Recommendations
    buys = recs_df.sort_values("predicted_5d_return", ascending=False).head(5).copy()
    sells = recs_df.sort_values("predicted_5d_return", ascending=True).head(5).copy()
    
    # 6. Generate Markdown Report
    print("\n Creating latest recommendations markdown report...")
    report_path = Path("docs/latest_recommendations.md")
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Investment Recommendations Engine — Report ({latest_date_str})\n\n")
        f.write(f"This report presents the ranked investment recommendations generated by our registered Ridge Regression model based on market indicators on **{latest_date_str}**.\n\n")
        
        f.write("## 🟢 Top 5 Buy Opportunities (Long)\n\n")
        f.write("| Ticker | Predicted 5D Return | Confidence Score | Risk Level | Top Contributors |\n")
        f.write("| :--- | :---: | :---: | :---: | :--- |\n")
        for _, r in buys.iterrows():
            f.write(f"| **{r['symbol']}** | {r['predicted_5d_return']:.2%} | {r['confidence_score']:.1f}% | {r['risk_score']} | {r['explainability']} |\n")
            
        f.write("\n## 🔴 Bottom 5 Sell/Short Opportunities (Short)\n\n")
        f.write("| Ticker | Predicted 5D Return | Confidence Score | Risk Level | Top Contributors |\n")
        f.write("| :--- | :---: | :---: | :---: | :--- |\n")
        for _, r in sells.iterrows():
            f.write(f"| **{r['symbol']}** | {r['predicted_5d_return']:.2%} | {r['confidence_score']:.1f}% | {r['risk_score']} | {r['explainability']} |\n")
            
        f.write("\n\n*Confidence Score is determined by signal strength compared to overall cross-sectional predictions. Risk level is derived from historical 20-day price volatility.*")
        
    print(f"    Saved report locally to {report_path}")
    
    # 7. Write Recommendations Table to Gold layer
    final_output_df = pd.concat([buys, sells]).reset_index(drop=True)
    final_output_df["date"] = latest_date_str
    
    print("\n Materializing recommendations table to Gold layer...")
    write_gold_delta(final_output_df, "recommendations")
    print("    Recommendations written successfully to S3/AWS Gold layer!")
    
    print("\n" + "=" * 65)
    print(" TOP ACTIONABLE OPPORTUNITIES")
    print("=" * 65)
    print(" BUYS:")
    for _, r in buys.iterrows():
        print(f"   - {r['symbol']}: Pred Return: {r['predicted_5d_return']:.2%}, Risk: {r['risk_score']}, Conf: {r['confidence_score']:.1f}%")
    print("[WARNING] SELLS:")
    for _, r in sells.iterrows():
        print(f"   - {r['symbol']}: Pred Return: {r['predicted_5d_return']:.2%}, Risk: {r['risk_score']}, Conf: {r['confidence_score']:.1f}%")
    print("=" * 65)
    
    print("\n Phase 11 — Recommendation Engine completed successfully!")


if __name__ == "__main__":
    main()
