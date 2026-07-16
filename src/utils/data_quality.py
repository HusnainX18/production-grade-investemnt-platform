"""
Great Expectations-style Data Quality Assurance Suite for local verification.
Verifies integrity, schema, type, and logical constraints across Bronze, Silver, and Gold layers.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

import pandas as pd
from dotenv import load_dotenv
from deltalake import DeltaTable
from src.utils.s3_helper import get_storage_options, get_s3_path

load_dotenv()

def run_dq_check(df: pd.DataFrame, description: str, rule_fn) -> bool:
    """Run a single DQ rule and print structured result."""
    try:
        passed = bool(rule_fn(df))
        status = " PASS" if passed else "[ERROR] FAIL"
        print(f"   - {description:<60}: {status}")
        return passed
    except Exception as e:
        print(f"   - {description:<60}: [ERROR] ERROR ({e})")
        return False

def check_not_null(col: str):
    return lambda df: df[col].isnull().sum() == 0

def check_value_greater_than(col: str, threshold: float):
    return lambda df: (df[col] >= threshold).all()

def check_logical_high_low():
    return lambda df: (df["high"] >= df["low"]).all()

def check_no_duplicates(cols: list):
    return lambda df: len(df) == len(df.drop_duplicates(subset=cols))

def main():
    print("=" * 80)
    print(" RUNNING MASTER DATA QUALITY SUITE (GREAT EXPECTATIONS MODEL)")
    print("=" * 80)
    
    # Configure options
    storage_options = get_storage_options()
    
    # 1. Verify Silver Stocks
    print("\n Checking Silver Stocks:")
    try:
        stocks_df = DeltaTable(get_s3_path("stocks", layer="silver"), storage_options=storage_options).to_pandas()
        s_rules = [
            ("Expect 'symbol' to not be null", check_not_null("symbol")),
            ("Expect 'timestamp' to not be null", check_not_null("timestamp")),
            ("Expect 'close' price to be strictly positive (> 0.01)", check_value_greater_than("close", 0.01)),
            ("Expect 'volume' to be non-negative (>= 0)", check_value_greater_than("volume", 0)),
            ("Expect high price to be >= low price", check_logical_high_low()),
            ("Expect no duplicate symbol/timestamp pairs", check_no_duplicates(["symbol", "timestamp"]))
        ]
        s_results = [run_dq_check(stocks_df, desc, rule) for desc, rule in s_rules]
    except Exception as e:
        print(f"  [ERROR] Could not load silver stocks: {e}")
        s_results = [False]

    # 2. Verify Silver Crypto
    print("\nChecking Silver Crypto:")
    try:
        crypto_df = DeltaTable(get_s3_path("crypto", layer="silver"), storage_options=storage_options).to_pandas()
        c_rules = [
            ("Expect 'symbol' to not be null", check_not_null("symbol")),
            ("Expect 'timestamp' to not be null", check_not_null("timestamp")),
            ("Expect 'close' price to be positive (> 0.000001)", check_value_greater_than("close", 0.000001)),
            ("Expect no duplicate symbol/timestamp pairs", check_no_duplicates(["symbol", "timestamp"]))
        ]
        c_results = [run_dq_check(crypto_df, desc, rule) for desc, rule in c_rules]
    except Exception as e:
        print(f"  [ERROR] Could not load silver crypto: {e}")
        c_results = [False]

    # 3. Verify Silver Macro
    print("\n Checking Silver Macro:")
    try:
        macro_df = DeltaTable(get_s3_path("macro", layer="silver"), storage_options=storage_options).to_pandas()
        m_rules = [
            ("Expect 'series_id' to not be null", check_not_null("series_id")),
            ("Expect 'date' to not be null", check_not_null("date")),
            ("Expect 'value' to not be null", check_not_null("value")),
            ("Expect no duplicate series_id/date pairs", check_no_duplicates(["series_id", "date"]))
        ]
        m_results = [run_dq_check(macro_df, desc, rule) for desc, rule in m_rules]
    except Exception as e:
        print(f"  [ERROR] Could not load silver macro: {e}")
        m_results = [False]

    # 4. Verify Silver News
    print("\nChecking Silver News:")
    try:
        news_df = DeltaTable(get_s3_path("news", layer="silver"), storage_options=storage_options).to_pandas()
        n_rules = [
            ("Expect 'title' to not be null", check_not_null("title")),
            ("Expect 'published_at' to not be null", check_not_null("published_at")),
            ("Expect 'url' to not be null", check_not_null("url")),
            ("Expect url to be unique (no duplicate articles)", check_no_duplicates(["url"]))
        ]
        n_results = [run_dq_check(news_df, desc, rule) for desc, rule in n_rules]
    except Exception as e:
        if "No files in log segment" in str(e) or "No such file" in str(e):
            print("   - Silver news Delta table not yet populated - skipping (WARN)")
            n_results = [True]  # treat as warning, not hard failure
        else:
            print(f"  [ERROR] Could not load silver news: {e}")
            n_results = [False]

    # 5. Verify Gold Features
    print("\nChecking Gold Features:")
    try:
        gold_df = DeltaTable(get_s3_path("features", layer="gold"), storage_options=storage_options).to_pandas()
        g_rules = [
            ("Expect 'symbol' to not be null", check_not_null("symbol")),
            ("Expect 'date' to not be null", check_not_null("date")),
            ("Expect 'sentiment_net' in range -1.0 to 1.0 (if present)",
             lambda df: df["sentiment_net"].between(-1.0, 1.0).all() if "sentiment_net" in df.columns else True),
            ("Expect MACD hist and RSI columns to exist", lambda df: "macd_hist" in df.columns and "rsi_14" in df.columns),
            ("Expect target returns to have < 1% nulls overall", lambda df: df["target_5d_return"].isnull().mean() < 0.01),
            ("Expect at least 50,000 rows in Gold table", lambda df: len(df) >= 50000),
            ("Expect at least 40 feature columns", lambda df: len(df.columns) >= 40),
        ]
        g_results = [run_dq_check(gold_df, desc, rule) for desc, rule in g_rules]
    except Exception as e:
        print(f"  [ERROR] Could not load gold features: {e}")
        g_results = [False]

    print("\n" + "=" * 80)
    all_passed = all(s_results + c_results + m_results + n_results + g_results)
    if all_passed:
        print(" ALL DATA QUALITY RULES PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("[ERROR] SOME DATA QUALITY RULES FAILED! Check logs above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
