"""
Silver Layer Data Quality Verification.
Verifies Silver Delta tables (stocks, crypto, macro, news) against data quality rules.
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
from src.utils.data_quality import (
    run_dq_check,
    check_not_null,
    check_value_greater_than,
    check_logical_high_low,
    check_no_duplicates,
)

load_dotenv()

def main():
    print("=" * 80)
    print(" RUNNING SILVER LAYER DATA QUALITY SUITE")
    print("=" * 80)
    
    storage_options = get_storage_options()
    results = []

    # 1. Verify Silver Stocks
    print("\nChecking Silver Stocks:")
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
        results.extend([run_dq_check(stocks_df, desc, rule) for desc, rule in s_rules])
    except Exception as e:
        print(f"  [ERROR] Could not load silver stocks: {e}")
        results.append(False)

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
        results.extend([run_dq_check(crypto_df, desc, rule) for desc, rule in c_rules])
    except Exception as e:
        print(f"  [ERROR] Could not load silver crypto: {e}")
        results.append(False)

    # 3. Verify Silver Macro
    print("\nChecking Silver Macro:")
    try:
        macro_df = DeltaTable(get_s3_path("macro", layer="silver"), storage_options=storage_options).to_pandas()
        m_rules = [
            ("Expect 'series_id' to not be null", check_not_null("series_id")),
            ("Expect 'date' to not be null", check_not_null("date")),
            ("Expect 'value' to not be null", check_not_null("value")),
            ("Expect no duplicate series_id/date pairs", check_no_duplicates(["series_id", "date"]))
        ]
        results.extend([run_dq_check(macro_df, desc, rule) for desc, rule in m_rules])
    except Exception as e:
        print(f"  [ERROR] Could not load silver macro: {e}")
        results.append(False)

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
        results.extend([run_dq_check(news_df, desc, rule) for desc, rule in n_rules])
    except Exception as e:
        if "No files in log segment" in str(e) or "No such file" in str(e):
            print("   - Silver news Delta table not yet populated - skipping (WARN)")
            results.append(True)
        else:
            print(f"  [ERROR] Could not load silver news: {e}")
            results.append(False)

    print("\n" + "=" * 80)
    if all(results):
        print(" ALL SILVER DATA QUALITY RULES PASSED!")
        sys.exit(0)
    else:
        print("[ERROR] SOME SILVER DATA QUALITY RULES FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
