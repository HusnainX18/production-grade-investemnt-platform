"""
Gold Layer Data Quality Verification.
Verifies Gold features Delta table against data quality rules.
"""

import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from deltalake import DeltaTable

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.s3_helper import get_storage_options, get_s3_path
from src.utils.data_quality import run_dq_check, check_not_null

load_dotenv()

def main():
    print("=" * 80)
    print(" RUNNING GOLD LAYER DATA QUALITY SUITE")
    print("=" * 80)
    
    storage_options = get_storage_options()
    results = []

    # Verify Gold Features
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
        results.extend([run_dq_check(gold_df, desc, rule) for desc, rule in g_rules])
    except Exception as e:
        print(f"  [ERROR] Could not load gold features: {e}")
        results.append(False)

    print("\n" + "=" * 80)
    if all(results):
        print(" ALL GOLD DATA QUALITY RULES PASSED!")
        sys.exit(0)
    else:
        print("[ERROR] SOME GOLD DATA QUALITY RULES FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
