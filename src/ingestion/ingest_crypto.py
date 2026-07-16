"""
Alpaca Crypto Historical Data Ingestion (Bronze Layer).
Ingests 5 years of daily OHLCV bars for 10 crypto assets into AWS S3 Data Lake.
No API credentials required for Alpaca crypto data.
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
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.models import BarSet
from src.utils.s3_helper import write_bronze_delta, get_s3_path


CRYPTO_SYMBOL_MAP = {
    "bitcoin":     "BTC/USD",
    "ethereum":    "ETH/USD",
    "binancecoin": "BNB/USD",
    "ripple":      "XRP/USD",
    "cardano":     "ADA/USD",
    "solana":      "SOL/USD",
    "polkadot":    "DOT/USD",
    "dogecoin":    "DOGE/USD",
    "avalanche-2": "AVAX/USD",
    "chainlink":   "LINK/USD",
}


def main() -> None:
    load_dotenv()

    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    crypto_coins = config["assets"]["crypto"]
    alpaca_symbols = [CRYPTO_SYMBOL_MAP[c] for c in crypto_coins if c in CRYPTO_SYMBOL_MAP]

    end_date = datetime.today()
    start_date = end_date - timedelta(days=5 * 365)

    print("=" * 60)
    print("Crypto Historical Ingestion (Bronze Layer)")
    print("=" * 60)
    print(f"Date Range : {start_date.date()} -> {end_date.date()}")
    print(f"Symbols    : {alpaca_symbols}")
    print(f"Destination: {get_s3_path('crypto')}")
    print("=" * 60)

    client = CryptoHistoricalDataClient()
    print(f"\nFetching {len(alpaca_symbols)} crypto assets in one request...")

    try:
        request = CryptoBarsRequest(
            symbol_or_symbols=alpaca_symbols,
            timeframe=TimeFrame.Day,
            start=start_date,
            end=end_date,
        )
        response = client.get_crypto_bars(request)
        if not isinstance(response, BarSet):
            raise ValueError(f"Unexpected response type from Alpaca: {type(response)}")
        df = response.df.reset_index()
        print(f"   Retrieved {len(df):,} rows")

    except Exception as e:
        print(f"  [ERROR] Fetch failed: {e}")
        sys.exit(1)

    df.columns = [c.lower() for c in df.columns]
    df["ingestion_timestamp"] = datetime.now(timezone.utc).isoformat()
    df["data_source"] = "alpaca"
    df["asset_class"] = "crypto"
    df["timestamp"] = df["timestamp"].astype(str)

    print(f"\n Total rows   : {len(df):,}")
    print(f" Unique symbols: {df['symbol'].nunique()}")
    print(f" Symbols found : {sorted(df['symbol'].unique().tolist())}")

    write_bronze_delta(df, "crypto", mode="overwrite")

    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f" Successful symbols  : {df['symbol'].nunique()}")
    print(f"📅 Date range          : {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print(f"📦 Total rows          : {len(df):,}")
    print(f"📦 AWS Storage path  : {get_s3_path('crypto')}")
    print("=" * 60)


if __name__ == "__main__":
    main()