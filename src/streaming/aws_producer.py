"""
AWS Kinesis Market Data Producer.
Streams live stock and crypto trade data (or simulated ticks) to AWS Kinesis.
"""

import os
import sys
import json
import time
import random
from datetime import datetime, timezone
from pathlib import Path
import boto3
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def run_simulator(kinesis_client, stream_name):
    """Generate synthetic trade ticks and publish them to Kinesis indefinitely."""
    print("=" * 60)
    print(" STARTING AWS KINESIS STREAMING PRODUCER (SIMULATOR)")
    print(f"   Stream Name : {stream_name}")
    print("=" * 60)

    prices = {
        "AAPL":    180.50,
        "MSFT":    415.20,
        "GOOGL":   173.80,
        "AMZN":    182.10,
        "NVDA":    920.40,
        "BTC-USD": 64250.00,
        "ETH-USD": 3450.00,
        "SOL-USD": 145.20,
    }

    try:
        while True:
            symbol = random.choice(list(prices.keys()))
            pct_change = random.uniform(-0.0015, 0.0015)
            new_price = round(prices[symbol] * (1 + pct_change), 2)
            prices[symbol] = new_price

            size = (
                round(random.uniform(0.001, 0.75), 4)
                if "USD" in symbol or "-" in symbol
                else random.randint(1, 100)
            )

            payload = {
                "symbol":    symbol,
                "price":     new_price,
                "size":      size,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source":    "simulator",
            }

            print(f"  [KINESIS PRODUCER] {symbol:<7} | Price: ${new_price:<9,} | Size: {size:<7} | Sent ")

            # Publish to AWS Kinesis
            kinesis_client.put_record(
                StreamName=stream_name,
                Data=json.dumps(payload),
                PartitionKey=symbol
            )

            time.sleep(random.uniform(0.3, 1.2))

    except KeyboardInterrupt:
        print("\n Producer stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Error in stream loop: {e}")
        sys.exit(1)

def main():
    load_dotenv()
    
    stream_name = "marketpulse-market-ticks"
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    kinesis_client = boto3.client("kinesis", region_name=region)
    
    run_simulator(kinesis_client, stream_name)

if __name__ == "__main__":
    main()
