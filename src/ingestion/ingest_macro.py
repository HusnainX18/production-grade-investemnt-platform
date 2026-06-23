"""
FRED Macroeconomic Data Ingestion (Bronze Layer).
Ingests 10 macroeconomic indicators from FRED into S3.
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

import time
import yaml
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from src.utils.s3_helper import write_bronze_delta, get_s3_path
from src.utils.api_helper import get_resilient_session


MACRO_SERIES = {
    "FEDFUNDS":   "Federal Funds Rate",
    "CPIAUCSL":   "Consumer Price Index (CPI)",
    "UNRATE":     "Unemployment Rate",
    "GDP":        "Gross Domestic Product",
    "DGS10":      "10-Year Treasury Yield",
    "DGS2":       "2-Year Treasury Yield",
    "VIXCLS":     "CBOE Volatility Index (VIX)",
    "M2SL":       "M2 Money Supply",
    "DCOILWTICO": "WTI Crude Oil Price",
    "DEXUSEU":    "USD/EUR Exchange Rate",
}

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def main() -> None:
    load_dotenv()

    fred_api_key = os.getenv("FRED_API_KEY")

    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=5 * 365)).strftime("%Y-%m-%d")

    print("=" * 60)
    print("Macro Historical Ingestion (Bronze Layer)")
    print("=" * 60)
    print(f"Date Range  : {start_date} -> {end_date}")
    print(f"Series      : {len(MACRO_SERIES)} indicators")
    print(f"Destination : {get_s3_path('macro')}")
    print("=" * 60)

    session = get_resilient_session()
    all_frames = []
    failed = []

    for series_id, series_name in MACRO_SERIES.items():
        print(f"\nFetching: {series_id} — {series_name}")

        try:
            params = {
                "series_id":         series_id,
                "api_key":           fred_api_key,
                "file_type":         "json",
                "observation_start": start_date,
                "observation_end":   end_date,
            }

            response = session.get(FRED_BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            observations = response.json().get("observations", [])

            if not observations:
                print(f"  ⚠️  No data returned for {series_id}")
                failed.append(series_id)
                continue

            df = pd.DataFrame(observations)
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna(subset=["value"])
            df["series_id"] = series_id
            df["series_name"] = series_name
            df["ingestion_timestamp"] = datetime.now().isoformat()
            df["data_source"] = "fred"
            df = df[["date", "value", "series_id", "series_name", "ingestion_timestamp", "data_source"]]

            all_frames.append(df)
            print(f"  ✅ Retrieved {len(df):,} observations")

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            failed.append(series_id)

        time.sleep(0.5)

    if not all_frames:
        print("\n❌ No data retrieved. Check your FRED API key.")
        sys.exit(1)

    combined_df = pd.concat(all_frames, ignore_index=True)

    print(f"\n📊 Total rows    : {len(combined_df):,}")
    print(f"📊 Unique series : {combined_df['series_id'].nunique()}")

    write_bronze_delta(combined_df, "macro", mode="overwrite")

    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"✅ Successful series : {combined_df['series_id'].nunique()}")
    print(f"❌ Failed series     : {failed if failed else 'None'}")
    print(f"📅 Date range        : {combined_df['date'].min()} -> {combined_df['date'].max()}")
    print(f"📦 Total rows        : {len(combined_df):,}")
    print(f"🪣 S3 path           : {get_s3_path('macro')}")
    print("=" * 60)


if __name__ == "__main__":
    main()