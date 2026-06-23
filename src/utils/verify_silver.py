"""
Phase 5 - Silver Layer Verification
Reads all 4 Delta tables from the S3 Silver layer and prints a health summary.
"""

import os
import sys
import yaml
import pandas as pd
from dotenv import load_dotenv
from deltalake import DeltaTable
from src.utils.s3_helper import get_storage_options, get_s3_path

def verify_table(table_name):
    print(f"\n📂 SILVER {table_name.upper()} TABLE")
    s3_path = get_s3_path(table_name, layer="silver")
    print(f"   Path: {s3_path}")
    
    try:
        dt = DeltaTable(s3_path, storage_options=get_storage_options())
        df = dt.to_pandas()
        
        # Check counts
        rows = len(df)
        cols = list(df.columns)
        null_pct = df.isnull().mean().mean() * 100
        
        # Determine date ranges & unique key counts
        if table_name == "stocks" or table_name == "crypto":
            date_range = f"{df['timestamp'].min()} -> {df['timestamp'].max()}"
            uniques = f"{df['symbol'].nunique()} unique symbols"
        elif table_name == "macro":
            date_range = f"{df['date'].min()} -> {df['date'].max()}"
            uniques = f"{df['series_id'].nunique()} unique series"
        elif table_name == "news":
            date_range = f"{df['published_at'].min()[:10]} -> {df['published_at'].max()[:10]}"
            uniques = f"{df['source'].nunique()} unique publishers"
            
        print(f"   ✅ Status       : HEALTHY")
        print(f"   📦 Rows         : {rows:,}")
        print(f"   📋 Columns      : {len(cols)} -> {cols}")
        print(f"   🔍 Null %       : {null_pct:.2f}%")
        print(f"   📈 Coverage     : {uniques}")
        print(f"   📅 Date range   : {date_range}")
        
        return rows, True
        
    except Exception as e:
        print(f"   ❌ Status       : CORRUPT / MISSING")
        print(f"   ❌ Error        : {e}")
        return 0, False

def main():
    load_dotenv()
    
    print("=" * 65)
    print("PHASE 5 — SILVER LAYER VERIFICATION REPORT")
    print("=" * 65)
    
    tables = ["stocks", "crypto", "macro", "news"]
    total_rows = 0
    all_healthy = True
    
    for t in tables:
        rows, healthy = verify_table(t)
        total_rows += rows
        if not healthy:
            all_healthy = False
            
    print("\n" + "=" * 65)
    print("SILVER LAYER HEALTH SUMMARY")
    print("=" * 65)
    print(f"📦 Total rows across all tables : {total_rows:,}")
    print(f"🗂️  Tables verified             : {len(tables)}/{len(tables)}")
    if all_healthy:
        print(f"✅ OVERALL STATUS               : ALL TABLES HEALTHY")
    else:
        print(f"❌ OVERALL STATUS               : DEGRADED (some tables failed)")
    print("=" * 65)

if __name__ == "__main__":
    main()
