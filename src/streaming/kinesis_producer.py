"""
AWS Kinesis Market Data Producer.
Streams live stock and crypto trade data (or simulated ticks) to AWS Kinesis.

Modes:
  simulator (default) — generates synthetic price ticks 24/7.
  live                — subscribes to the Alpaca live crypto stream.
                        Falls back to simulator on credential/import failure.

Usage:
  python kinesis_producer.py           # simulator mode
  python kinesis_producer.py --live    # live Alpaca stream
  STREAMING_MODE=live python ...       # live mode via env var
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

import json
import time
import random
import yaml
import argparse
import boto3
from datetime import datetime, timezone
from dotenv import load_dotenv


def _build_kinesis_client(aws_access_key: str, aws_secret_key: str, aws_region: str):
    """Initialise and return a boto3 Kinesis client."""
    return boto3.client(
        "kinesis",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region,
    )


def run_simulator(kinesis_client, stream_name: str, aws_region: str) -> None:
    """
    Generate synthetic trade ticks and publish them to Kinesis indefinitely.
    Allows pipeline testing 24/7, even when markets are closed.
    """
    print("=" * 60)
    print("🚀 STARTING KINESIS STREAMING PRODUCER (SIMULATOR)")
    print(f"   Stream : {stream_name}")
    print(f"   Region : {aws_region}")
    print("=" * 60)

    prices = {
        "AAPL":    180.50,
        "MSFT":    415.20,
        "GOOGL":   173.80,
        "AMZN":    182.10,
        "NVDA":    920.40,
        "BTC/USD": 64250.00,
        "ETH/USD": 3450.00,
        "SOL/USD": 145.20,
    }

    try:
        while True:
            symbol = random.choice(list(prices.keys()))
            pct_change = random.uniform(-0.0015, 0.0015)
            new_price = round(prices[symbol] * (1 + pct_change), 2)
            prices[symbol] = new_price

            size = (
                round(random.uniform(0.001, 0.75), 4)
                if "USD" in symbol
                else random.randint(1, 100)
            )

            payload = {
                "symbol":    symbol,
                "price":     new_price,
                "size":      size,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source":    "simulator",
            }

            print(f"  [STREAM] {symbol:<7} | Price: ${new_price:<9,} | Size: {size:<7} | Sent ✅")

            kinesis_client.put_record(
                StreamName=stream_name,
                Data=json.dumps(payload),
                PartitionKey=symbol,
            )

            time.sleep(random.uniform(0.3, 1.5))

    except KeyboardInterrupt:
        print("\n👋 Producer stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Simulator error: {e}")
        sys.exit(1)


def run_live(kinesis_client, stream_name: str, aws_region: str) -> None:
    """
    Subscribe to the Alpaca live crypto stream and forward trade records to Kinesis.
    Falls back to simulator mode if credentials are missing or the library is unavailable.
    """
    print("=" * 60)
    print("🚀 STARTING KINESIS STREAMING PRODUCER (LIVE ALPACA)")
    print(f"   Stream : {stream_name}")
    print(f"   Region : {aws_region}")
    print("=" * 60)

    try:
        from alpaca.data.live import CryptoDataStream
    except ImportError:
        print("❌ 'alpaca-py' not found. Falling back to simulator mode...")
        run_simulator(kinesis_client, stream_name, aws_region)
        return

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        print("⚠️  Alpaca credentials missing. Falling back to simulator mode...")
        run_simulator(kinesis_client, stream_name, aws_region)
        return

    try:
        crypto_stream = CryptoDataStream(api_key, secret_key)

        async def trade_handler(data):
            payload = {
                "symbol":    data.symbol,
                "price":     float(data.price),
                "size":      float(data.size),
                "timestamp": data.timestamp.isoformat(),
                "source":    "alpaca_live",
            }
            print(f"  [LIVE] {data.symbol:<7} | Price: ${data.price:<9,} | Size: {data.size:<7} | Sent ✅")
            kinesis_client.put_record(
                StreamName=stream_name,
                Data=json.dumps(payload),
                PartitionKey=data.symbol,
            )

        crypto_stream.subscribe_trades(trade_handler, "BTC/USD", "ETH/USD")
        print("📡 Connected to Alpaca Crypto Live Feed. Listening for ticks...")
        crypto_stream.run()

    except Exception as e:
        print(f"❌ Live streaming error: {e}. Falling back to simulator mode...")
        run_simulator(kinesis_client, stream_name, aws_region)


def main() -> None:
    load_dotenv()

    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    stream_name = config["aws"]["kinesis_stream"]

    try:
        kinesis_client = _build_kinesis_client(aws_access_key, aws_secret_key, aws_region)
    except Exception as e:
        print(f"❌ Failed to initialise Kinesis client: {e}")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Kinesis Market Data Producer")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Attempt live stream from Alpaca (defaults to simulator)",
    )
    args = parser.parse_args()

    mode = os.getenv("STREAMING_MODE", "simulator")

    if args.live or mode == "live":
        run_live(kinesis_client, stream_name, aws_region)
    else:
        run_simulator(kinesis_client, stream_name, aws_region)


if __name__ == "__main__":
    main()
