"""
Bronze Layer Data Quality Verification.
Verifies that Bronze Delta tables exist and contain records.
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
    print(" RUNNING BRONZE LAYER DATA QUALITY SUITE")
    print("=" * 80)
    
    storage_options = get_storage_options()
    results = []

    # Verify Bronze Stocks
    print("\nChecking Bronze Stocks:")
    try:
        df = DeltaTable(get_s3_path("stocks", layer="bronze"), storage_options=storage_options).to_pandas()
        rules = [
            ("Expect 'symbol' to not be null", check_not_null("symbol")),
            ("Expect 'timestamp' to not be null", check_not_null("timestamp")),
            ("Expect row count to be positive", lambda df: len(df) > 0)
        ]
        results.extend([run_dq_check(df, desc, rule) for desc, rule in rules])
    except Exception as e:
        print(f"  [ERROR] Could not load bronze stocks: {e}")
        results.append(False)

    # Verify Bronze Crypto
    print("\nChecking Bronze Crypto:")
    try:
        df = DeltaTable(get_s3_path("crypto", layer="bronze"), storage_options=storage_options).to_pandas()
        rules = [
            ("Expect 'symbol' to not be null", check_not_null("symbol")),
            ("Expect 'timestamp' to not be null", check_not_null("timestamp")),
            ("Expect row count to be positive", lambda df: len(df) > 0)
        ]
        results.extend([run_dq_check(df, desc, rule) for desc, rule in rules])
    except Exception as e:
        print(f"  [ERROR] Could not load bronze crypto: {e}")
        results.append(False)

    # Verify Bronze Macro
    print("\nChecking Bronze Macro:")
    try:
        df = DeltaTable(get_s3_path("macro", layer="bronze"), storage_options=storage_options).to_pandas()
        rules = [
            ("Expect 'series_id' to not be null", check_not_null("series_id")),
            ("Expect 'date' to not be null", check_not_null("date")),
            ("Expect row count to be positive", lambda df: len(df) > 0)
        ]
        results.extend([run_dq_check(df, desc, rule) for desc, rule in rules])
    except Exception as e:
        print(f"  [ERROR] Could not load bronze macro: {e}")
        results.append(False)

    # Verify Bronze News
    print("\nChecking Bronze News:")
    try:
        df = DeltaTable(get_s3_path("news", layer="bronze"), storage_options=storage_options).to_pandas()
        rules = [
            ("Expect 'title' to not be null", check_not_null("title")),
            ("Expect 'published_at' to not be null", check_not_null("published_at")),
            ("Expect row count to be positive", lambda df: len(df) > 0)
        ]
        results.extend([run_dq_check(df, desc, rule) for desc, rule in rules])
    except Exception as e:
        print(f"  [ERROR] Could not load bronze news: {e}")
        results.append(False)

    print("\n" + "=" * 80)
    if all(results):
        print(" ALL BRONZE DATA QUALITY RULES PASSED!")
        sys.exit(0)
    else:
        print("[ERROR] SOME BRONZE DATA QUALITY RULES FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
