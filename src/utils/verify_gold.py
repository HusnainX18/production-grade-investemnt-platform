"""
Phase 6 - Gold Layer Verification
Reads the Delta table from the S3 Gold layer and prints a health summary.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
from dotenv import load_dotenv
from deltalake import DeltaTable
from src.utils.s3_helper import get_storage_options, get_s3_path

def main():
    load_dotenv()
    
    print("=" * 65)
    print("PHASE 6 — GOLD LAYER VERIFICATION REPORT")
    print("=" * 65)
    
    s3_path = get_s3_path("features", layer="gold")
    print(f"   Path: {s3_path}")
    
    try:
        dt = DeltaTable(s3_path, storage_options=get_storage_options())
        df = dt.to_pandas()
        
        # Check counts
        rows = len(df)
        cols = list(df.columns)
        null_counts = df.isnull().sum()
        
        print(f"   ✅ Status       : HEALTHY")
        print(f"   📦 Rows         : {rows:,}")
        print(f"   📋 Columns      : {len(cols)}")
        print(f"   📈 Coverage     : {df['symbol'].nunique()} unique symbols")
        
        # Date range
        date_range = f"{df['date'].min()} -> {df['date'].max()}"
        print(f"   📅 Date range   : {date_range}")
        
        print("\n📊 Column Details & Nulls:")
        for col in cols:
            nulls = null_counts[col]
            pct = (nulls / rows) * 100
            print(f"   - {col:<20} | Nulls: {nulls:,} ({pct:.2f}%)")
            
        print("\n📈 Sample Data (First 3 rows):")
        # Ensure we only print existing sample columns
        sample_cols = ["symbol", "date", "close"]
        extra_cols = ["rsi_14", "macd", "yield_curve_slope", "sentiment_net", "target_1d_return", "target_5d_return"]
        for c in extra_cols:
            if c in df.columns:
                sample_cols.append(c)
        print(df[sample_cols].head(3).to_string(index=False))
        
    except Exception as e:
        print(f"   ❌ Status       : CORRUPT / MISSING")
        print(f"   ❌ Error        : {e}")

if __name__ == "__main__":
    main()
