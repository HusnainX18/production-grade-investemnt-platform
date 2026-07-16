"""
AWS Kinesis to DynamoDB Feature Store Consumer.
Consumes price ticks from Kinesis and updates DynamoDB Feature Store in real-time.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import boto3
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def run_consumer(kinesis_client, dynamo_client, stream_name, table_name):
    """Consume from Kinesis and write to DynamoDB indefinitely."""
    print("=" * 60)
    print(" STARTING AWS KINESIS TO DYNAMODB CONSUMER")
    print(f"   Stream   : {stream_name}")
    print(f"   DynamoDB : {table_name}")
    print("=" * 60)

    # 1. Get Shard Iterator
    try:
        response = kinesis_client.describe_stream(StreamName=stream_name)
        shard_id = response['StreamDescription']['Shards'][0]['ShardId']
        
        iterator_resp = kinesis_client.get_shard_iterator(
            StreamName=stream_name,
            ShardId=shard_id,
            ShardIteratorType='LATEST'
        )
        shard_iterator = iterator_resp['ShardIterator']
    except Exception as e:
        print(f"[ERROR] Failed to initialize stream details: {e}")
        sys.exit(1)

    print(" Listening for live Kinesis ticks...")
    try:
        while True:
            records_response = kinesis_client.get_records(
                ShardIterator=shard_iterator,
                Limit=10
            )
            
            records = records_response.get('Records', [])
            for record in records:
                payload = json.loads(record['Data'].decode('utf-8'))
                symbol = payload['symbol']
                price = payload['price']
                size = payload['size']
                timestamp_str = payload['timestamp']
                
                # Format date as YYYY-MM-DD for DynamoDB Sort Key
                date_str = timestamp_str[:10]
                
                print(f"  [KINESIS CONSUMER] Received {symbol:<7} | Price: ${price:<9} | Caching in DynamoDB...")
                
                # 2. Write to DynamoDB Feature Store
                try:
                    dynamo_client.put_item(
                        TableName=table_name,
                        Item={
                            'symbol': {'S': symbol},
                            'date': {'S': date_str},
                            'price': {'N': str(price)},
                            'size': {'N': str(size)},
                            'last_updated': {'S': timestamp_str},
                            'feature_source': {'S': 'realtime_stream'}
                        }
                    )
                    print(f"      Cached {symbol} successfully!")
                except Exception as db_err:
                    print(f"     [ERROR] DynamoDB Write Error: {db_err}")
            
            # Update shard iterator to pull next batch
            shard_iterator = records_response.get('NextShardIterator')
            if not shard_iterator:
                break
                
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\n Consumer stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Consumer Error: {e}")
        sys.exit(1)

def main():
    load_dotenv()
    
    stream_name = "marketpulse-market-ticks"
    table_name = "marketpulse-feature-store"
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    kinesis_client = boto3.client("kinesis", region_name=region)
    dynamo_client = boto3.client("dynamodb", region_name=region)
    
    run_consumer(kinesis_client, dynamo_client, stream_name, table_name)

if __name__ == "__main__":
    main()
