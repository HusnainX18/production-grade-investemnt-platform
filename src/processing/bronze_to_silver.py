"""
Bronze-to-Silver Data Processing Pipeline.

Reads raw Bronze Delta tables from AWS S3 Data Lake, applies cleaning and standardisation,
validates data quality with native pandas checks, and writes cleaned data to
Silver layer Delta tables.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore
    except Exception:
        pass

import yaml
import pandas as pd
from typing import Union
from dotenv import load_dotenv
from deltalake import DeltaTable
from src.utils.s3_helper import get_storage_options, get_s3_path, write_silver_delta


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

def _check_not_null(df: pd.DataFrame, col: str) -> tuple[bool, str]:
    """Return (passed, message) for a not-null check on a column."""
    n = df[col].isnull().sum()
    passed = n == 0
    msg = f"not_null({col})"
    if not passed:
        msg += f"  [ERROR]  {n:,} nulls found"
    return passed, msg


def _check_between(
    df: pd.DataFrame,
    col: str,
    min_value: Union[int, float],
) -> tuple[bool, str]:
    """Return (passed, message) for a minimum-value range check on a column."""
    n = (df[col] < min_value).sum()
    passed = n == 0
    msg = f"min_value({col} >= {min_value})"
    if not passed:
        msg += f"  [ERROR]  {n:,} rows below threshold"
    return passed, msg


def _check_column_exists(df: pd.DataFrame, col: str) -> tuple[bool, str]:
    """Return (passed, message) for a column-existence check."""
    passed = col in df.columns
    msg = f"column_exists({col})"
    if not passed:
        msg += "  [ERROR]  column missing"
    return passed, msg


def validate_dataset(
    df: pd.DataFrame,
    checks: list[tuple[bool, str]],
    dataset_name: str,
) -> bool:
    """
    Run a list of (bool, message) check tuples and print a per-rule summary.

    Args:
        df:           The DataFrame to validate.
        checks:       List of (passed: bool, message: str) tuples.
        dataset_name: Human-readable label used in log output.

    Returns:
        True if all checks pass, False otherwise.
    """
    print(f"\n Running data quality checks for: {dataset_name.upper()}")
    passed_count = sum(1 for ok, _ in checks if ok)
    failed_count = len(checks) - passed_count
    print(f"    Results: {passed_count} passed, {failed_count} failed")

    all_passed = failed_count == 0
    if not all_passed:
        print(f"   [WARNING]  Data quality warnings in {dataset_name}!")
        for ok, msg in checks:
            if not ok:
                print(f"      [ERROR] Failed: {msg}")
    else:
        print("    All checks passed.")

    return all_passed


# ---------------------------------------------------------------------------
# Per-dataset validation suites
# ---------------------------------------------------------------------------

def validate_stocks(df: pd.DataFrame) -> bool:
    checks = [
        _check_not_null(df, "symbol"),
        _check_not_null(df, "timestamp"),
        _check_between(df, "close", 0.01),
        _check_between(df, "volume", 0),
        _check_column_exists(df, "sector"),
        _check_column_exists(df, "industry"),
    ]
    return validate_dataset(df, checks, "stocks")


def validate_crypto(df: pd.DataFrame) -> bool:
    checks = [
        _check_not_null(df, "symbol"),
        _check_not_null(df, "timestamp"),
        _check_between(df, "close", 0.000001),
        _check_between(df, "volume", 0),
    ]
    return validate_dataset(df, checks, "crypto")


def validate_macro(df: pd.DataFrame) -> bool:
    checks = [
        _check_not_null(df, "series_id"),
        _check_not_null(df, "date"),
        _check_not_null(df, "value"),
    ]
    return validate_dataset(df, checks, "macro")


def validate_news(df: pd.DataFrame) -> bool:
    checks = [
        _check_not_null(df, "title"),
        _check_not_null(df, "published_at"),
        _check_not_null(df, "url"),
    ]
    return validate_dataset(df, checks, "news")


# ---------------------------------------------------------------------------
# Processing functions
# ---------------------------------------------------------------------------

def process_stocks(sectors_map: dict[str, dict[str, str]]) -> bool:
    """Read, clean, validate, and write the Silver stocks table."""
    print("\n--- Processing Stocks ---")
    try:
        dt = DeltaTable(get_s3_path("stocks", layer="bronze"), storage_options=get_storage_options())
        df = dt.to_pandas()
    except Exception as e:
        print(f"[ERROR] Failed to read Bronze stocks: {e}")
        return False

    print(f"   Read {len(df):,} raw rows from Bronze.")

    df = df.drop_duplicates(subset=["symbol", "timestamp"])
    df["timestamp"] = pd.Series(pd.to_datetime(df["timestamp"])).dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["symbol", "timestamp", "close"])

    def get_sector_info(ticker: str) -> pd.Series:  # type: ignore[type-arg]
        info = sectors_map.get(ticker, {"sector": "Unknown", "industry": "Unknown"})
        return pd.Series([info["sector"], info["industry"]])

    # Use explicit DataFrame construction to avoid the ambiguous DataFrame|Series
    # return type that Pyright infers from a bare .apply() on a Series.
    sector_data = pd.DataFrame(
        df["symbol"].apply(get_sector_info).values.tolist(),
        columns=["sector", "industry"],
        index=df.index,
    )
    df["sector"] = sector_data["sector"]
    df["industry"] = sector_data["industry"]

    validate_stocks(df)
    write_silver_delta(df, "stocks", mode="overwrite")
    print("    Stocks Silver layer written successfully.")
    return True


def process_crypto() -> bool:
    """Read, clean, validate, and write the Silver crypto table."""
    print("\n--- Processing Crypto ---")
    try:
        dt = DeltaTable(get_s3_path("crypto", layer="bronze"), storage_options=get_storage_options())
        df = dt.to_pandas()
    except Exception as e:
        print(f"[ERROR] Failed to read Bronze crypto: {e}")
        return False

    print(f"   Read {len(df):,} raw rows from Bronze.")

    df = df.drop_duplicates(subset=["symbol", "timestamp"])
    df["timestamp"] = pd.Series(pd.to_datetime(df["timestamp"], errors="coerce")).dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["symbol", "timestamp", "close"])

    validate_crypto(df)
    write_silver_delta(df, "crypto", mode="overwrite")
    print("    Crypto Silver layer written successfully.")
    return True


def process_macro() -> bool:
    """Read, clean, validate, and write the Silver macro table."""
    print("\n--- Processing Macro ---")
    try:
        dt = DeltaTable(get_s3_path("macro", layer="bronze"), storage_options=get_storage_options())
        df = dt.to_pandas()
    except Exception as e:
        print(f"[ERROR] Failed to read Bronze macro: {e}")
        return False

    print(f"   Read {len(df):,} raw rows from Bronze.")

    df = df.drop_duplicates(subset=["series_id", "date"])
    df["date"] = pd.Series(pd.to_datetime(df["date"], errors="coerce")).dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["series_id", "date", "value"])

    validate_macro(df)
    write_silver_delta(df, "macro", mode="overwrite")
    print("    Macro Silver layer written successfully.")
    return True


def process_news() -> bool:
    """Read, clean, validate, and write the Silver news table."""
    print("\n--- Processing News ---")
    try:
        dt = DeltaTable(get_s3_path("news", layer="bronze"), storage_options=get_storage_options())
        df = dt.to_pandas()
    except Exception as e:
        print(f"[ERROR] Failed to read Bronze news: {e}")
        return False

    print(f"   Read {len(df):,} raw rows from Bronze.")

    df = df.drop_duplicates(subset=["url"])
    df["description"] = df["description"].fillna("")
    df["matched_tickers"] = df["matched_tickers"].fillna("")
    df = df.dropna(subset=["title", "published_at", "url"])

    validate_news(df)
    write_silver_delta(df, "news", mode="overwrite")
    print("    News Silver layer written successfully.")
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

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
        print(f"[ERROR] Failed to load {sectors_path}: {e}")
        sys.exit(1)

    results = [
        process_stocks(sectors_map),
        process_crypto(),
        process_macro(),
        process_news(),
    ]

    print("\n" + "=" * 65)
    if all(results):
        print(" Bronze to Silver pipeline completed successfully!")
    else:
        print("[ERROR] Pipeline completed with ERRORS. Check log output above.")
    print("=" * 65)


if __name__ == "__main__":
    main()
