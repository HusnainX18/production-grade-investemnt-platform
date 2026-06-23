"""
Alpaca Stock Historical Data Ingestion (Bronze Layer).
Ingests 5 years of daily OHLCV bars for 50 equities into S3.
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
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from src.utils.s3_helper import write_bronze_delta, get_s3_path


def main() -> None:
    load_dotenv()

    alpaca_api_key = os.getenv("ALPACA_API_KEY")
    alpaca_secret = os.getenv("ALPACA_SECRET_KEY")

    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    tickers = config["assets"]["equities"]

    end_date = datetime.today()
    start_date = end_date - timedelta(days=5 * 365)

    print("=" * 60)
    print("Stock Historical Ingestion (Bronze Layer)")
    print("=" * 60)
    print(f"Date Range : {start_date.date()} -> {end_date.date()}")
    print(f"Tickers    : {len(tickers)} stocks")
    print(f"Feed       : IEX (free tier)")
    print(f"Destination: {get_s3_path('stocks')}")
    print("=" * 60)

    client = StockHistoricalDataClient(api_key=alpaca_api_key, secret_key=alpaca_secret)

    batch_size = 10
    all_frames = []
    failed = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        print(f"\nFetching batch {i // batch_size + 1}: {batch}")

        try:
            request = StockBarsRequest(
                symbol_or_symbols=batch,
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date,
                feed=DataFeed.IEX,
            )
            bars = client.get_stock_bars(request)
            df = bars.df.reset_index()
            all_frames.append(df)
            print(f"  ✅ Retrieved {len(df):,} rows")

        except Exception as e:
            print(f"  ❌ Batch failed: {e}")
            failed.extend(batch)

        time.sleep(2)

    if not all_frames:
        print("\n❌ No data retrieved. Check your API keys.")
        sys.exit(1)

    combined_df = pd.concat(all_frames, ignore_index=True)
    combined_df.columns = [c.lower() for c in combined_df.columns]
    combined_df["ingestion_timestamp"] = datetime.utcnow().isoformat()
    combined_df["data_source"] = "alpaca"
    combined_df["asset_class"] = "equity"
    combined_df["timestamp"] = combined_df["timestamp"].astype(str)

    print(f"\n📊 Total rows    : {len(combined_df):,}")
    print(f"📊 Unique tickers: {combined_df['symbol'].nunique()}")

    write_bronze_delta(combined_df, "stocks", mode="overwrite")

    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"✅ Successful tickers : {combined_df['symbol'].nunique()}")
    print(f"❌ Failed tickers     : {failed if failed else 'None'}")
    print(f"📅 Date range         : {combined_df['timestamp'].min()} -> {combined_df['timestamp'].max()}")
    print(f"📦 Total rows         : {len(combined_df):,}")
    print(f"🪣 S3 path            : {get_s3_path('stocks')}")
    print("=" * 60)


if __name__ == "__main__":
    main()