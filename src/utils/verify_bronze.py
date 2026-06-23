"""
Bronze Layer Verification Script.
Reads all 4 Bronze Delta tables from S3 and prints a health summary.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import yaml
from dotenv import load_dotenv
from deltalake import DeltaTable


def main() -> None:
    load_dotenv()

    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    bucket_name = config["aws"]["s3_bucket"]

    storage_options = {
        "AWS_ACCESS_KEY_ID": aws_access_key,
        "AWS_SECRET_ACCESS_KEY": aws_secret_key,
        "AWS_REGION": aws_region,
    }

    tables = {
        "Stocks": f"s3://{bucket_name}/bronze/stocks",
        "Crypto": f"s3://{bucket_name}/bronze/crypto",
        "Macro":  f"s3://{bucket_name}/bronze/macro",
        "News":   f"s3://{bucket_name}/bronze/news",
    }

    print("=" * 65)
    print("BRONZE LAYER VERIFICATION REPORT")
    print("=" * 65)

    total_rows = 0
    all_passed = True

    for table_name, s3_path in tables.items():
        print(f"\n📂 {table_name.upper()} TABLE")
        print(f"   Path: {s3_path}")

        try:
            dt = DeltaTable(s3_path, storage_options=storage_options)
            df = dt.to_pandas()

            row_count = len(df)
            col_count = len(df.columns)
            null_pct = df.isnull().sum().sum() / (row_count * col_count) * 100
            total_rows += row_count

            print(f"   ✅ Status       : HEALTHY")
            print(f"   📦 Rows         : {row_count:,}")
            print(f"   📋 Columns      : {col_count} → {list(df.columns)}")
            print(f"   🔍 Null %       : {null_pct:.2f}%")

            if table_name == "Stocks":
                print(f"   📈 Tickers      : {df['symbol'].nunique()} unique")
                print(f"   📅 Date range   : {df['timestamp'].min()[:10]} → {df['timestamp'].max()[:10]}")

            elif table_name == "Crypto":
                print(f"   🪙 Symbols      : {df['symbol'].nunique()} unique → {sorted(df['symbol'].unique().tolist())}")
                print(f"   📅 Date range   : {df['timestamp'].min()[:10]} → {df['timestamp'].max()[:10]}")

            elif table_name == "Macro":
                print(f"   📊 Series       : {df['series_id'].nunique()} unique → {sorted(df['series_id'].unique().tolist())}")
                print(f"   📅 Date range   : {df['date'].min()} → {df['date'].max()}")

            elif table_name == "News":
                print(f"   📰 Sources      : {df['source'].nunique()} unique")
                print(f"   📅 Date range   : {df['published_at'].min()[:10]} → {df['published_at'].max()[:10]}")

        except Exception as e:
            print(f"   ❌ Status       : FAILED")
            print(f"   Error          : {e}")
            all_passed = False

    print("\n" + "=" * 65)
    print("BRONZE LAYER HEALTH SUMMARY")
    print("=" * 65)
    print(f"📦 Total rows across all tables : {total_rows:,}")
    print(f"🗂️  Tables verified             : {len(tables)}/4")
    if all_passed:
        print("✅ OVERALL STATUS               : ALL TABLES HEALTHY")
    else:
        print("❌ OVERALL STATUS               : SOME TABLES HAVE ISSUES")
    print("=" * 65)


if __name__ == "__main__":
    main()