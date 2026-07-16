"""
AWS Infrastructure Setup Script.

Provisions all required AWS services for the Investment Platform project:
  - S3 Bucket with Medallion Architecture folders
  - IAM User, Policy, and Programmatic Access Keys
  - Kinesis Data Stream (2 shards)
  - CloudWatch Billing Alarm

Run this script ONCE after creating a new AWS account to restore the
full infrastructure. It is safe to re-run: it skips resources that
already exist.

Usage:
    .venv\\Scripts\\python scripts/setup_aws_infrastructure.py
"""

import os
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import yaml
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError


# ── Configuration ──────────────────────────────────────────────────────────────

load_dotenv()

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION     = os.getenv("AWS_REGION", "us-east-1")

with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

S3_BUCKET        = config["aws"]["s3_bucket"]
KINESIS_STREAM   = config["aws"]["kinesis_stream"]
IAM_USER_NAME    = "investment-platform-user"
IAM_POLICY_NAME  = "investment-platform-policy"

# ── Boto3 Clients ───────────────────────────────────────────────────────────────

session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION,
)

s3         = session.client("s3")
iam        = session.client("iam")
kinesis    = session.client("kinesis")
cloudwatch = session.client("cloudwatch")


# ── Helper ──────────────────────────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print(f"{'=' * 65}")


# ── Step 1: S3 Bucket ───────────────────────────────────────────────────────────

def create_s3_bucket() -> None:
    section("STEP 1: Creating S3 Bucket")
    print(f"   Bucket name : {S3_BUCKET}")
    print(f"   Region      : {AWS_REGION}")

    try:
        if AWS_REGION == "us-east-1":
            s3.create_bucket(Bucket=S3_BUCKET)
        else:
            s3.create_bucket(
                Bucket=S3_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
            )
        print(f"    Bucket created: s3://{S3_BUCKET}")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"    Bucket already exists: s3://{S3_BUCKET}")
        else:
            print(f"   [ERROR] Bucket creation failed: {e}")
            sys.exit(1)

    # Create Medallion folder structure (S3 uses empty placeholder objects)
    folders = [
        "bronze/stocks/",
        "bronze/crypto/",
        "bronze/macro/",
        "bronze/news/",
        "silver/stocks/",
        "silver/crypto/",
        "silver/macro/",
        "silver/news/",
        "gold/features/",
        "streaming/live_market_stream/",
        "checkpoints/live_market_stream/",
    ]
    print("\n   Creating folder structure...")
    for folder in folders:
        s3.put_object(Bucket=S3_BUCKET, Key=folder, Body=b"")
        print(f"    s3://{S3_BUCKET}/{folder}")

    print("\n    S3 bucket and folder structure ready.")


# ── Step 2: IAM User + Policy + Access Keys ─────────────────────────────────────

def create_iam_user() -> tuple[str, str]:
    section("STEP 2: Creating IAM User & Policy")

    # Create User
    try:
        iam.create_user(UserName=IAM_USER_NAME)
        print(f"    IAM User created: {IAM_USER_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"    IAM User already exists: {IAM_USER_NAME}")
        else:
            print(f"   [ERROR] IAM User creation failed: {e}")
            sys.exit(1)

    # Define permissions policy
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect":   "Allow",
                "Action":   ["s3:*"],
                "Resource": [
                    f"arn:aws:s3:::{S3_BUCKET}",
                    f"arn:aws:s3:::{S3_BUCKET}/*",
                ],
            },
            {
                "Effect":   "Allow",
                "Action":   [
                    "kinesis:PutRecord",
                    "kinesis:PutRecords",
                    "kinesis:GetRecords",
                    "kinesis:GetShardIterator",
                    "kinesis:DescribeStream",
                    "kinesis:ListStreams",
                    "kinesis:ListShards",
                ],
                "Resource": f"arn:aws:kinesis:{AWS_REGION}:*:stream/{KINESIS_STREAM}",
            },
            {
                "Effect":   "Allow",
                "Action":   ["cloudwatch:PutMetricAlarm", "cloudwatch:DescribeAlarms"],
                "Resource": "*",
            },
        ],
    }

    # Create or update the policy
    try:
        account_id = session.client("sts").get_caller_identity()["Account"]
        policy_arn = f"arn:aws:iam::{account_id}:policy/{IAM_POLICY_NAME}"
        iam.create_policy(
            PolicyName=IAM_POLICY_NAME,
            PolicyDocument=json.dumps(policy_document),
        )
        print(f"    IAM Policy created: {IAM_POLICY_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"    IAM Policy already exists: {IAM_POLICY_NAME}")
        else:
            print(f"   [ERROR] IAM Policy creation failed: {e}")
            sys.exit(1)

    # Attach the policy to the user
    try:
        iam.attach_user_policy(UserName=IAM_USER_NAME, PolicyArn=policy_arn)
        print(f"    Policy attached to user: {IAM_USER_NAME}")
    except ClientError as e:
        print(f"   [WARNING] Could not attach policy (may already be attached): {e}")

    # Create programmatic Access Keys
    try:
        keys = iam.create_access_key(UserName=IAM_USER_NAME)["AccessKey"]
        new_access_key = keys["AccessKeyId"]
        new_secret_key = keys["SecretAccessKey"]
        print(f"\n   🔑 NEW Access Key ID     : {new_access_key}")
        print(f"   🔑 NEW Secret Access Key : {new_secret_key}")
        print("\n   [WARNING]  IMPORTANT: Copy these keys NOW — AWS only shows the Secret Key once!")
        return new_access_key, new_secret_key
    except ClientError as e:
        print(f"   [WARNING] Could not create access key: {e}")
        return "", ""


# ── Step 3: Kinesis Data Stream ─────────────────────────────────────────────────

def create_kinesis_stream() -> None:
    section("STEP 3: Creating Kinesis Data Stream")
    print(f"   Stream name : {KINESIS_STREAM}")
    print(f"   Shards      : 2")

    try:
        kinesis.create_stream(StreamName=KINESIS_STREAM, ShardCount=2)
        print(f"   ⏳ Stream creation initiated. Waiting for ACTIVE state...")

        # Wait for the stream to become ACTIVE
        for _ in range(30):
            desc = kinesis.describe_stream(StreamName=KINESIS_STREAM)
            status = desc["StreamDescription"]["StreamStatus"]
            if status == "ACTIVE":
                print(f"    Kinesis Stream is ACTIVE: {KINESIS_STREAM}")
                return
            print(f"      Current status: {status}. Waiting 5 seconds...")
            time.sleep(5)
        print("   [WARNING] Stream is taking longer than expected. Check the AWS console.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"    Kinesis Stream already exists: {KINESIS_STREAM}")
        else:
            print(f"   [ERROR] Kinesis stream creation failed: {e}")
            sys.exit(1)


# ── Step 4: CloudWatch Billing Alarm ────────────────────────────────────────────

def create_billing_alarm() -> None:
    section("STEP 4: Creating CloudWatch Billing Alarm")
    alarm_name = "investment-platform-billing-alarm"
    threshold  = 10.0  # USD

    try:
        cloudwatch.put_metric_alarm(
            AlarmName           = alarm_name,
            AlarmDescription    = "Triggers when AWS charges exceed $10",
            MetricName          = "EstimatedCharges",
            Namespace           = "AWS/Billing",
            Statistic           = "Maximum",
            Dimensions          = [{"Name": "Currency", "Value": "USD"}],
            Period              = 86400,   # 24 hours
            EvaluationPeriods   = 1,
            Threshold           = threshold,
            ComparisonOperator  = "GreaterThanThreshold",
            TreatMissingData    = "notBreaching",
        )
        print(f"    CloudWatch billing alarm set at ${threshold:.2f} threshold.")
    except ClientError as e:
        print(f"   [WARNING] CloudWatch alarm creation failed: {e}")
        print("   (Billing alerts may require enabling in us-east-1 region)")


# ── Step 5: Write Updated .env ──────────────────────────────────────────────────

def update_env_file(new_access_key: str, new_secret_key: str) -> None:
    section("STEP 5: Updating .env With New IAM User Keys")

    if not new_access_key or not new_secret_key:
        print("   [WARNING] No new keys generated. Skipping .env update.")
        return

    env_path = Path(".env")
    env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""

    lines = env_text.splitlines()
    updated_lines = []
    keys_updated  = {"AWS_ACCESS_KEY_ID": False, "AWS_SECRET_ACCESS_KEY": False}

    for line in lines:
        if line.startswith("AWS_ACCESS_KEY_ID="):
            updated_lines.append(f"AWS_ACCESS_KEY_ID={new_access_key}")
            keys_updated["AWS_ACCESS_KEY_ID"] = True
        elif line.startswith("AWS_SECRET_ACCESS_KEY="):
            updated_lines.append(f"AWS_SECRET_ACCESS_KEY={new_secret_key}")
            keys_updated["AWS_SECRET_ACCESS_KEY"] = True
        else:
            updated_lines.append(line)

    if not keys_updated["AWS_ACCESS_KEY_ID"]:
        updated_lines.append(f"AWS_ACCESS_KEY_ID={new_access_key}")
    if not keys_updated["AWS_SECRET_ACCESS_KEY"]:
        updated_lines.append(f"AWS_SECRET_ACCESS_KEY={new_secret_key}")

    env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    print(f"    .env updated with new IAM user access keys.")
    print("   [WARNING] Your ROOT admin keys should be removed from .env after verification.")


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 65)
    print("  AWS INFRASTRUCTURE SETUP — Investment Platform")
    print("=" * 65)

    if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
        print("\n[ERROR] AWS credentials are missing from .env!")
        print("   Add AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to .env first.")
        sys.exit(1)

    create_s3_bucket()
    new_access_key, new_secret_key = create_iam_user()
    create_kinesis_stream()
    create_billing_alarm()
    update_env_file(new_access_key, new_secret_key)

    print("\n" + "=" * 65)
    print("   AWS INFRASTRUCTURE SETUP COMPLETE!")
    print("=" * 65)
    print("""
NEXT STEPS — Run these commands in order to rebuild all data:

  1. Re-ingest Bronze data:
     .venv\\Scripts\\python src/ingestion/ingest_stocks.py
     .venv\\Scripts\\python src/ingestion/ingest_crypto.py
     .venv\\Scripts\\python src/ingestion/ingest_macro.py
     .venv\\Scripts\\python src/ingestion/ingest_news.py

  2. Verify Bronze tables:
     .venv\\Scripts\\python src/utils/verify_bronze.py

  3. Process Silver layer:
     .venv\\Scripts\\python src/processing/bronze_to_silver.py

  4. Process Gold layer:
     .venv\\Scripts\\python src/processing/silver_to_gold.py

  5. Verify all layers:
     .venv\\Scripts\\python src/utils/verify_silver.py
     .venv\\Scripts\\python src/utils/verify_gold.py
""")


if __name__ == "__main__":
    main()
