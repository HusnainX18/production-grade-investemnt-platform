"""
Local S3 Connection Verification Script.
Validates AWS credentials and writes a test object to the configured S3 bucket.
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
import boto3
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    config_path = os.path.join("config", "config.yaml")
    if not os.path.exists(config_path):
        print(f"❌ Config file not found at {config_path}")
        return

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    bucket_name = config["aws"]["s3_bucket"]
    stream_name = config["aws"]["kinesis_stream"]

    print("--- Local Connection Verification ---")
    print(f"S3 Bucket    : {bucket_name}")
    print(f"Kinesis Stream: {stream_name}")
    print(f"AWS Region   : {aws_region}")

    if not aws_access_key or not aws_secret_key:
        print("❌ AWS credentials are missing from your .env file!")
        return

    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region,
        )

        s3_client.put_object(
            Bucket=bucket_name,
            Key="checkpoints/local_connection_test.txt",
            Body="Local machine S3 connection verification: SUCCESS!",
        )
        print("✅ Local Python script connected to S3 and wrote test file!")

    except Exception as e:
        print(f"❌ Failed to connect or write to S3: {e}")


if __name__ == "__main__":
    main()