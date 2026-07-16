"""
Silver-to-Gold Feature Engineering Pipeline.

Loads Silver Delta tables (stocks, crypto, macro, news) from AWS S3 Data Lake, computes technical indicators,
macroeconomic features, and FinBERT daily sentiment, merges them on date/ticker,
calculates target variables, and writes the unified feature table to the AWS S3 Data Lake Gold layer.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore
    except Exception:
        pass

import yaml
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from deltalake import DeltaTable

from src.utils.s3_helper import get_storage_options, get_s3_path, write_gold_delta

# Global flag and classifier reference for FinBERT
use_finbert = False
_classifier = None

try:
    print(" Attempting to load Hugging Face transformers for FinBERT...")
    from transformers import pipeline
    import torch

    # Use CPU for reliability in containerised environments without NVIDIA drivers
    device = 0 if torch.cuda.is_available() else -1
    print(f"   PyTorch loaded successfully. CUDA available: {torch.cuda.is_available()} (Using device: {device})")

    print(" Loading FinBERT model (yiyanghkust/finbert-tone)...")
    _classifier = pipeline(
        "text-classification",
        model="yiyanghkust/finbert-tone",
        tokenizer="yiyanghkust/finbert-tone",
        device=device,
        top_k=None,  # Return all class scores
    )
    use_finbert = True
    print("    FinBERT loaded successfully!")
except Exception as ex:
    print(f"   [WARNING] FinBERT load failed or transformers not fully installed: {ex}")
    print("   [WARNING] Falling back to local rule-based lexicon for news sentiment.")
    use_finbert = False


def load_silver_table(table_name: str) -> pd.DataFrame:
    """Read a Silver Delta table from AWS S3 Data Lake and return a Pandas DataFrame."""
    s3_path = get_s3_path(table_name, layer="silver")
    print(f" Loading Silver {table_name.upper()} table from {s3_path}...")
    try:
        dt = DeltaTable(s3_path, storage_options=get_storage_options())
        return dt.to_pandas()
    except Exception as e:
        print(f"   [WARNING] Could not load {table_name.upper()}: {e}")
        return pd.DataFrame()


def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate technical indicators and target variables grouped by asset symbol.
    
    Indicators: SMAs (20, 50, 200), RSI (14), MACD, Bollinger Bands, rolling returns (1d, 5d, 20d),
    price volatility, volume ratio, 52-week price position, momentum acceleration, volatility regime ratio,
    relative strength vs sector, and target smooth returns.
    """
    print(" Computing technical indicators & targets...")
    df = df.sort_values(["symbol", "timestamp"]).copy()
    
    # Pre-allocate columns
    cols_to_add = [
        "sma_20", "sma_50", "sma_200", "rsi_14", "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_lower", "bb_width", "return_1d", "return_5d", "return_20d",
        "volatility_20d", "volume_ratio", "price_position_52w", "momentum_acceleration",
        "vol_regime_ratio", "target_1d_return", "target_5d_return", "target_smooth_return"
    ]
    for c in cols_to_add:
        df[c] = np.nan
        
    for symbol, group in df.groupby("symbol"):
        close = group["close"]
        volume = group["volume"]
        
        # Simple Moving Averages
        sma_20 = close.rolling(window=20).mean()
        sma_50 = close.rolling(window=50).mean()
        sma_200 = close.rolling(window=200).mean()
        
        # Relative Strength Index (RSI - 14d)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        
        # MACD (12, 26, 9)
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        macd = ema_12 - ema_26
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - macd_signal
        
        # Bollinger Bands (20d, 2 std)
        sma_bb = close.rolling(window=20).mean()
        std_bb = close.rolling(window=20).std()
        bb_upper = sma_bb + (2 * std_bb)
        bb_lower = sma_bb - (2 * std_bb)
        bb_width = (bb_upper - bb_lower) / (sma_bb + 1e-9)
        
        # Rolling Returns
        ret_1d = close.pct_change(periods=1)
        ret_5d = close.pct_change(periods=5)
        ret_20d = close.pct_change(periods=20)
        
        # Price Volatility (20d rolling standard deviation of 1d returns)
        vol_20d = ret_1d.rolling(window=20).std()
        
        # 1. Volume Ratio (today's volume vs 20d moving average)
        vol_mean_20 = volume.rolling(window=20).mean()
        volume_ratio = volume / (vol_mean_20 + 1e-9)

        # 2. Price Position 52w (252 trading days)
        min_52w = close.rolling(window=252, min_periods=20).min()
        max_52w = close.rolling(window=252, min_periods=20).max()
        price_position_52w = (close - min_52w) / (max_52w - min_52w + 1e-9)

        # 3. Momentum Acceleration
        momentum_acceleration = ret_5d - ret_20d

        # 4. Volatility Regime Ratio (5d std vs 60d std)
        vol_std_5 = ret_1d.rolling(window=5).std()
        vol_std_60 = ret_1d.rolling(window=60).std()
        vol_regime_ratio = vol_std_5 / (vol_std_60 + 1e-9)

        # Target variables (forward-looking returns)
        t_1d = close.shift(-1) / close - 1.0
        t_3d = close.shift(-3) / close - 1.0
        t_5d = close.shift(-5) / close - 1.0
        t_10d = close.shift(-10) / close - 1.0
        
        # Target smooth return is average of 3-day, 5-day and 10-day forward return
        target_smooth = (t_3d + t_5d + t_10d) / 3.0
        
        # Assign back
        idx = group.index
        df.loc[idx, "sma_20"] = sma_20
        df.loc[idx, "sma_50"] = sma_50
        df.loc[idx, "sma_200"] = sma_200
        df.loc[idx, "rsi_14"] = rsi
        df.loc[idx, "macd"] = macd
        df.loc[idx, "macd_signal"] = macd_signal
        df.loc[idx, "macd_hist"] = macd_hist
        df.loc[idx, "bb_upper"] = bb_upper
        df.loc[idx, "bb_lower"] = bb_lower
        df.loc[idx, "bb_width"] = bb_width
        df.loc[idx, "return_1d"] = ret_1d
        df.loc[idx, "return_5d"] = ret_5d
        df.loc[idx, "return_20d"] = ret_20d
        df.loc[idx, "volatility_20d"] = vol_20d
        df.loc[idx, "volume_ratio"] = volume_ratio
        df.loc[idx, "price_position_52w"] = price_position_52w
        df.loc[idx, "momentum_acceleration"] = momentum_acceleration
        df.loc[idx, "vol_regime_ratio"] = vol_regime_ratio
        df.loc[idx, "target_1d_return"] = t_1d
        df.loc[idx, "target_5d_return"] = t_5d
        df.loc[idx, "target_smooth_return"] = target_smooth

    # Compute Relative Strength vs Sector globally (requires cross-sectional grouping)
    df["rel_strength_sector"] = df["return_1d"] - df.groupby(["sector", "timestamp"])["return_1d"].transform("mean")
    cols_to_add.append("rel_strength_sector")

    # Explicitly cast technical columns as float
    for c in cols_to_add:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        
    return df


def compute_macro_features(macro_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot FRED macro series into columns and compute yield curve slope."""
    if macro_df.empty:
        return pd.DataFrame()
        
    print(" Computing macroeconomic indicators...")
    # Pivot series_id into unique columns
    pivot_df = macro_df.pivot(index="date", columns="series_id", values="value").reset_index()
    
    # Sort and forward-fill monthly/quarterly series to fill daily intervals
    pivot_df = pivot_df.sort_values("date")
    series_cols = [c for c in pivot_df.columns if c != "date"]
    pivot_df[series_cols] = pivot_df[series_cols].ffill()
    
    # Calculate yield curve slope if both 10y and 2y interest rates are available
    if "DGS10" in pivot_df.columns and "DGS2" in pivot_df.columns:
        pivot_df["yield_curve_slope"] = pivot_df["DGS10"] - pivot_df["DGS2"]
    else:
        pivot_df["yield_curve_slope"] = np.nan
        
    return pivot_df


def compute_lexicon_sentiment(text: str) -> dict:
    """Simple rule-based keyword matcher as a local CPU fallback for news sentiment."""
    pos_words = {"bullish", "growth", "profit", "surge", "gain", "rise", "positive", "beat", "upward", "boost", "success", "higher"}
    neg_words = {"bearish", "loss", "fall", "drop", "decline", "negative", "miss", "downward", "slump", "crash", "plunge", "lower"}
    
    words = set(text.lower().split())
    pos_count = len(words.intersection(pos_words))
    neg_count = len(words.intersection(neg_words))
    
    total = pos_count + neg_count
    if total == 0:
        return {"label": "Neutral", "score": 1.0}
    elif pos_count > neg_count:
        return {"label": "Positive", "score": pos_count / total}
    else:
        return {"label": "Negative", "score": neg_count / total}


def compute_news_sentiment(news_df: pd.DataFrame) -> pd.DataFrame:
    """Classify news using FinBERT (or local fallback) and aggregate daily sentiment per ticker."""
    if news_df.empty:
        return pd.DataFrame()
        
    print(f"📰 Computing sentiment scores for {len(news_df):,} articles...")
    headlines = news_df["title"].fillna("").tolist()
    sentiment_records = []
    
    if use_finbert and _classifier is not None:
        try:
            print("    Running FinBERT inference in batches...")
            results: list[list[dict[str, float | str]]] = _classifier(headlines, batch_size=32, truncation=True, max_length=512)  # type: ignore[assignment]

            for item in results:
                # top_k=None returns list of {label, score} dicts for all classes
                # Normalise: item may be a single dict or a list of dicts
                item_list: list[dict[str, float | str]] = [item] if isinstance(item, dict) else item
                scores = {str(d["label"]).lower(): d["score"] for d in item_list}
                pos = float(scores.get("positive", 0.0))
                neg = float(scores.get("negative", 0.0))
                neu = float(scores.get("neutral", 0.0))
                sentiment_records.append({
                    "sentiment_pos": pos,
                    "sentiment_neg": neg,
                    "sentiment_neu": neu,
                    "sentiment_net": pos - neg,
                })

            use_fallback = False
        except Exception as e:
            print(f"   [WARNING] FinBERT batch processing failed ({e}). Falling back to rule-based lexicon.")
            use_fallback = True
    else:
        use_fallback = True
        
    if use_fallback:
        print("   🏷️ Processing news using rule-based sentiment lexicon...")
        for h in headlines:
            res = compute_lexicon_sentiment(h)
            label = res["label"].lower()
            score = res["score"]
            
            pos = score if label == "positive" else 0.0
            neg = score if label == "negative" else 0.0
            neu = score if label == "neutral" else 0.0
            sentiment_records.append({
                "sentiment_pos": pos,
                "sentiment_neg": neg,
                "sentiment_neu": neu,
                "sentiment_net": pos - neg
            })
            
    sentiment_df = pd.DataFrame(sentiment_records)
    news_with_sent = pd.concat([news_df.reset_index(drop=True), sentiment_df], axis=1)
    
    # Split comma-separated matched tickers and explode
    news_with_sent["ticker"] = news_with_sent["matched_tickers"].str.split(",")
    exploded = news_with_sent.explode("ticker")
    exploded["ticker"] = exploded["ticker"].str.strip()
    exploded = exploded[exploded["ticker"] != ""]
    
    # Standardize date component of published_at
    exploded["date_str"] = pd.Series(pd.to_datetime(exploded["published_at"])).dt.strftime("%Y-%m-%d")
    
    # Aggregate average sentiment daily by ticker
    daily_sentiment = exploded.groupby(["ticker", "date_str"]).agg({
        "sentiment_pos": "mean",
        "sentiment_neg": "mean",
        "sentiment_neu": "mean",
        "sentiment_net": "mean"
    }).reset_index()
    
    return daily_sentiment


def main() -> None:
    load_dotenv()
    
    # Load all input datasets
    stocks = load_silver_table("stocks")
    crypto = load_silver_table("crypto")
    macro = load_silver_table("macro")
    news = load_silver_table("news")
    
    if stocks.empty:
        print("[ERROR] Essential stocks dataset is empty. Cannot compile features.")
        sys.exit(1)
        
    # Combine stock and crypto prices into a unified asset table
    stocks["asset_class"] = "equity"
    if not crypto.empty:
        crypto["asset_class"] = "crypto"
        prices = pd.concat([stocks, crypto], ignore_index=True)
    else:
        prices = stocks
        
    # 1. Compute technical indicators and targets
    features_df = compute_technical_indicators(prices)
    
    # Convert date keys to datetime for temporal alignment
    features_df["date_dt"] = pd.Series(pd.to_datetime(features_df["timestamp"].astype(str), errors="coerce"))
    
    # 2. Compute macro features and merge (Asof Join to prevent forward data leakage)
    macro_pivot = compute_macro_features(macro)
    if not macro_pivot.empty:
        macro_pivot["date_dt"] = pd.to_datetime(macro_pivot["date"])
        
        # Sort keys required for pd.merge_asof
        features_df = features_df.sort_values("date_dt")
        macro_pivot = macro_pivot.sort_values("date_dt")
        
        # Merge macro columns on nearest prior macro date
        features_df = pd.merge_asof(
            features_df,
            macro_pivot.drop(columns=["date"]),
            on="date_dt",
            direction="backward"
        )
        
    # 3. Compute daily sentiment scores and merge on ticker/date
    sentiment_df = compute_news_sentiment(news)
    if not sentiment_df.empty:
        features_df["date_dt"] = pd.Series(pd.to_datetime(features_df["date_dt"], errors="coerce"))
        features_df["date_str"] = pd.Series(pd.to_datetime(features_df["date_dt"])).dt.strftime("%Y-%m-%d")
        features_df = pd.merge(
            features_df,
            sentiment_df,
            left_on=["symbol", "date_str"],
            right_on=["ticker", "date_str"],
            how="left"
        )
        # Drop redundant merge keys
        features_df = features_df.drop(columns=["ticker", "date_str"])
    else:
        features_df["sentiment_pos"] = np.nan
        features_df["sentiment_neg"] = np.nan
        features_df["sentiment_neu"] = np.nan
        features_df["sentiment_net"] = np.nan

    # Fill missing sentiment scores with 0.0 (neutral default when no news exists)
    sentiment_cols = ["sentiment_pos", "sentiment_neg", "sentiment_neu", "sentiment_net"]
    for sc in sentiment_cols:
        features_df[sc] = features_df[sc].fillna(0.0)
        
    # Standardize final schema columns
    features_df["date"] = pd.Series(pd.to_datetime(features_df["date_dt"])).dt.strftime("%Y-%m-%d")
    
    # Drop intermediate datetime columns
    features_df = features_df.drop(columns=["date_dt", "timestamp"], errors="ignore")
    
    # Reorder columns logically
    first_cols = ["symbol", "date", "close", "asset_class"]
    other_cols = [c for c in features_df.columns if c not in first_cols]
    final_df = features_df[first_cols + other_cols]
    assert isinstance(final_df, pd.DataFrame)
    
    print(f"\n Generated {len(final_df):,} rows with {len(final_df.columns)} feature columns.")
    print(f" Missing values in target variables:")
    print(f"   - target_1d_return: {final_df['target_1d_return'].isnull().sum():,} nulls")
    print(f"   - target_5d_return: {final_df['target_5d_return'].isnull().sum():,} nulls")
    
    # Write to AWS Storage Gold Table
    write_gold_delta(final_df, "features", mode="overwrite")
    print(" Phase 6 - Gold Layer feature engineering completed successfully!")


if __name__ == "__main__":
    main()
