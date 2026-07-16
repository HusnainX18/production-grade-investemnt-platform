"""
Glue Crawler setup script.
Registers a Glue Crawler that scans S3 Bronze/Silver/Gold Delta Lake folders
and auto-populates the Glue Catalog database with table schemas.
Run this once to set up schema governance.
"""

import os
import sys
import time
import boto3
from dotenv import load_dotenv

load_dotenv()

REGION         = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
BUCKET         = "marketpulse-datalake-husnain"
GLUE_DB        = "marketpulse_lakehouse"
CRAWLER_NAME   = "marketpulse-s3-crawler"
GLUE_ROLE_ARN  = None   # auto-discovered below


def get_glue_role_arn(iam_client):
    """Discover the Glue crawler IAM role created by Terraform."""
    try:
        role = iam_client.get_role(RoleName="marketpulse-glue-crawler-role")
        return role["Role"]["Arn"]
    except Exception as e:
        print(f"[ERROR] Could not find Glue IAM role: {e}")
        sys.exit(1)


def create_or_update_crawler(glue_client, role_arn):
    """Create the Glue Crawler if it does not exist, otherwise update it."""
    targets = {
        "S3Targets": [
            {"Path": f"s3://{BUCKET}/bronze/"},
            {"Path": f"s3://{BUCKET}/silver/"},
            {"Path": f"s3://{BUCKET}/gold/"},
        ]
    }

    try:
        glue_client.get_crawler(Name=CRAWLER_NAME)
        print(f"Crawler '{CRAWLER_NAME}' already exists. Updating targets...")
        glue_client.update_crawler(
            Name=CRAWLER_NAME,
            Role=role_arn,
            DatabaseName=GLUE_DB,
            Targets=targets,
            TablePrefix="marketpulse_",
            SchemaChangePolicy={
                "UpdateBehavior": "UPDATE_IN_DATABASE",
                "DeleteBehavior": "LOG"
            }
        )
        print("Crawler updated successfully.")
    except glue_client.exceptions.EntityNotFoundException:
        print(f"Creating crawler '{CRAWLER_NAME}'...")
        glue_client.create_crawler(
            Name=CRAWLER_NAME,
            Role=role_arn,
            DatabaseName=GLUE_DB,
            Targets=targets,
            TablePrefix="marketpulse_",
            SchemaChangePolicy={
                "UpdateBehavior": "UPDATE_IN_DATABASE",
                "DeleteBehavior": "LOG"
            }
        )
        print("Crawler created successfully.")


def run_crawler(glue_client):
    """Start the crawler and wait for completion."""
    print(f"Starting crawler '{CRAWLER_NAME}'...")
    glue_client.start_crawler(Name=CRAWLER_NAME)

    print("Waiting for crawler to complete (this takes 1-3 minutes)...")
    while True:
        response = glue_client.get_crawler(Name=CRAWLER_NAME)
        state = response["Crawler"]["State"]
        print(f"  Crawler state: {state}")
        if state == "READY":
            break
        time.sleep(15)

    print("Crawler run completed.")


def list_discovered_tables(glue_client):
    """Print all tables discovered in the Glue Catalog."""
    print(f"\nTables in Glue Catalog database '{GLUE_DB}':")
    response = glue_client.get_tables(DatabaseName=GLUE_DB)
    tables = response.get("TableList", [])
    if not tables:
        print("  No tables found yet.")
    for table in tables:
        cols = len(table.get("StorageDescriptor", {}).get("Columns", []))
        print(f"  - {table['Name']} ({cols} columns)")


def main():
    print("=" * 60)
    print(" GLUE CATALOG CRAWLER SETUP")
    print("=" * 60)

    iam_client  = boto3.client("iam",  region_name=REGION)
    glue_client = boto3.client("glue", region_name=REGION)

    role_arn = get_glue_role_arn(iam_client)
    print(f"Using IAM role: {role_arn}")

    create_or_update_crawler(glue_client, role_arn)
    run_crawler(glue_client)
    list_discovered_tables(glue_client)

    print("\nGlue Catalog setup complete.")
    print(f"View in AWS Console: https://console.aws.amazon.com/glue/home?region={REGION}#/v2/data-catalog/databases/detail/{GLUE_DB}")


if __name__ == "__main__":
    main()
