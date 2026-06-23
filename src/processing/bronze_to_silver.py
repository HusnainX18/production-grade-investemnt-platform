"""
Bronze-to-Silver Data Processing Pipeline.

Reads raw Bronze Delta tables from S3, applies cleaning and standardisation,
validates data quality with Great Expectations, and writes cleaned data to
Silver layer Delta tables.
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
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from deltalake import DeltaTable
import great_expectations as ge
from src.utils.s3_helper import get_storage_options, get_s3_path, write_silver_delta


def validate_dataset(df: pd.DataFrame, expectation_suite_func, dataset_name: str) -> bool:
    """
    Wrap a DataFrame as a Great Expectations dataset, run validations, and
    print a per-rule summary.

    Args:
        df: The DataFrame to validate.
        expectation_suite_func: Callable that accepts a GE dataset and returns
            (bool success, list[ExpectationValidationResult]).
        dataset_name: Human-readable label used in log output.

    Returns:
        True if all expectations pass, False otherwise.
    """
    print(f"\n🔍 Running Great Expectations for: {dataset_name.upper()}")
    ge_df = ge.from_pandas(df)
    success, results = expectation_suite_func(ge_df)

    passed_count = sum(1 for r in results if r.success)
    failed_count = sum(1 for r in results if not r.success)
    print(f"   📊 Results: {passed_count} passed, {failed_count} failed")

    if not success:
        print(f"   ⚠️  Data quality warnings in {dataset_name}!")
        for r in results:
            if not r.success:
                col = r.expectation_config.kwargs.get("column", "Table-level")
                exp_type = r.expectation_config.expectation_type
                print(f"      ❌ Failed: {exp_type} on '{col}'")
    else:
        print("   ✅ All expectations passed.")

    return success


def validate_stocks_suite(ge_df) -> tuple:
    results = [
        ge_df.expect_column_values_to_not_be_null("symbol"),
        ge_df.expect_column_values_to_not_be_null("timestamp"),
        ge_df.expect_column_values_to_be_between("close", min_value=0.01),
        ge_df.expect_column_values_to_be_between("volume", min_value=0),
        ge_df.expect_column_to_exist("sector"),
        ge_df.expect_column_to_exist("industry"),
    ]
    return all(r.success for r in results), results


def validate_crypto_suite(ge_df) -> tuple:
    results = [
        ge_df.expect_column_values_to_not_be_null("symbol"),
        ge_df.expect_column_values_to_not_be_null("timestamp"),
        ge_df.expect_column_values_to_be_between("close", min_value=0.000001),
        ge_df.expect_column_values_to_be_between("volume", min_value=0),
    ]
    return all(r.success for r in results), results


def validate_macro_suite(ge_df) -> tuple:
    results = [
        ge_df.expect_column_values_to_not_be_null("series_id"),
        ge_df.expect_column_values_to_not_be_null("date"),
        ge_df.expect_column_values_to_not_be_null("value"),
    ]
    return all(r.success for r in results), results


def validate_news_suite(ge_df) -> tuple:
    results = [
        ge_df.expect_column_values_to_not_be_null("title"),
        ge_df.expect_column_values_to_not_be_null("published_at"),
        ge_df.expect_column_values_to_not_be_null("url"),
    ]
    return all(r.success for r in results), results


def process_stocks(sectors_map: dict) -> bool:
    """Read, clean, validate, and write the Silver stocks table."""
    print("\n--- Processing Stocks ---")
    try:
        dt = DeltaTable(get_s3_path("stocks", layer="bronze"), storage_options=get_storage_options())
        df = dt.to_pandas()
    except Exception as e:
        print(f"❌ Failed to read Bronze stocks: {e}")
        return False

    print(f"   Read {len(df):,} raw rows from Bronze.")

    df = df.drop_duplicates(subset=["symbol", "timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["symbol", "timestamp", "close"])

    def get_sector_info(ticker: str) -> pd.Series:
        info = sectors_map.get(ticker, {"sector": "Unknown", "industry": "Unknown"})
        return pd.Series([info["sector"], info["industry"]])

    df[["sector", "industry"]] = df["symbol"].apply(get_sector_info)

    validate_dataset(df, validate_stocks_suite, "stocks")
    write_silver_delta(df, "stocks", mode="overwrite")
    print("   ✅ Stocks Silver layer written successfully.")
    return True


def process_crypto() -> bool:
    """Read, clean, validate, and write the Silver crypto table."""
    print("\n--- Processing Crypto ---")
    try:
        dt = DeltaTable(get_s3_path("crypto", layer="bronze"), storage_options=get_storage_options())
        df = dt.to_pandas()
    except Exception as e:
        print(f"❌ Failed to read Bronze crypto: {e}")
        return False

    print(f"   Read {len(df):,} raw rows from Bronze.")

    df = df.drop_duplicates(subset=["symbol", "timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["symbol", "timestamp", "close"])

    validate_dataset(df, validate_crypto_suite, "crypto")
    write_silver_delta(df, "crypto", mode="overwrite")
    print("   ✅ Crypto Silver layer written successfully.")
    return True


def process_macro() -> bool:
    """Read, clean, validate, and write the Silver macro table."""
    print("\n--- Processing Macro ---")
    try:
        dt = DeltaTable(get_s3_path("macro", layer="bronze"), storage_options=get_storage_options())
        df = dt.to_pandas()
    except Exception as e:
        print(f"❌ Failed to read Bronze macro: {e}")
        return False

    print(f"   Read {len(df):,} raw rows from Bronze.")

    df = df.drop_duplicates(subset=["series_id", "date"])
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["series_id", "date", "value"])

    validate_dataset(df, validate_macro_suite, "macro")
    write_silver_delta(df, "macro", mode="overwrite")
    print("   ✅ Macro Silver layer written successfully.")
    return True


def process_news() -> bool:
    """Read, clean, validate, and write the Silver news table."""
    print("\n--- Processing News ---")
    try:
        dt = DeltaTable(get_s3_path("news", layer="bronze"), storage_options=get_storage_options())
        df = dt.to_pandas()
    except Exception as e:
        print(f"❌ Failed to read Bronze news: {e}")
        return False

    print(f"   Read {len(df):,} raw rows from Bronze.")

    df = df.drop_duplicates(subset=["url"])
    df["description"] = df["description"].fillna("")
    df["matched_tickers"] = df["matched_tickers"].fillna("")
    df = df.dropna(subset=["title", "published_at", "url"])

    validate_dataset(df, validate_news_suite, "news")
    write_silver_delta(df, "news", mode="overwrite")
    print("   ✅ News Silver layer written successfully.")
    return True


def main() -> None:
    load_dotenv()

    print("=" * 65)
    print("BRONZE TO SILVER DATA PROCESSING PIPELINE")
    print("=" * 65)

    sectors_path = "config/sectors.yaml"
    try:
        with open(sectors_path, "r") as f:
            sectors_config = yaml.safe_load(f)
        sectors_map = sectors_config.get("sectors", {})
    except Exception as e:
        print(f"❌ Failed to load {sectors_path}: {e}")
        sys.exit(1)

    results = [
        process_stocks(sectors_map),
        process_crypto(),
        process_macro(),
        process_news(),
    ]

    print("\n" + "=" * 65)
    if all(results):
        print("🎉 Bronze to Silver pipeline completed successfully!")
    else:
        print("❌ Pipeline completed with ERRORS. Check log output above.")
    print("=" * 65)


if __name__ == "__main__":
    main()
