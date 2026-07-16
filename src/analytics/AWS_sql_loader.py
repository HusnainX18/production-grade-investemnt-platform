"""
Amazon Redshift Serverless Ingestion Loader.
Loads Gold layer Delta tables from S3 into Amazon Redshift Serverless.
Triggered by Airflow or manual runs.
"""

import os
import sys
import time
from pathlib import Path
import boto3
import pandas as pd
from deltalake import DeltaTable
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.utils.s3_helper import get_s3_path, get_storage_options

load_dotenv()

REGION          = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
NAMESPACE       = "marketpulse-ns"
WORKGROUP       = "marketpulse-wg"
DB_NAME         = "marketpulse"
ADMIN_USER      = "admin"
ADMIN_PASSWORD  = "MarketPulse2026!"
BUCKET          = os.getenv("S3_BUCKET", "marketpulse-datalake-husnain")


def get_workgroup_endpoint(rs_client):
    """Retrieve Redshift Serverless workgroup endpoint details."""
    try:
        wg = rs_client.get_workgroup(workgroupName=WORKGROUP)
        status = wg["workgroup"]["status"]
        if status == "AVAILABLE":
            endpoint = wg["workgroup"]["endpoint"]["address"]
            port     = wg["workgroup"]["endpoint"]["port"]
            return endpoint, port
        else:
            print(f"Workgroup '{WORKGROUP}' status is {status}. Waiting...")
            return None, None
    except rs_client.exceptions.ResourceNotFoundException:
        print(f"[ERROR] Workgroup '{WORKGROUP}' not found. Run scripts/setup_redshift.py first to provision.")
        sys.exit(1)


def load_table_via_data_api(rs_data_client, workgroup, db, table_name, df):
    """Load a pandas DataFrame into Redshift using the Data API."""
    print(f"\nLoading '{table_name}' ({len(df):,} rows) into Redshift...")

    # Create table DDL from DataFrame dtypes
    type_map = {
        "int64": "BIGINT",
        "float64": "FLOAT8",
        "bool": "BOOLEAN",
        "object": "VARCHAR(512)",
        "datetime64[ns]": "TIMESTAMP",
    }
    cols_ddl = ", ".join(
        f"{col} {type_map.get(str(dtype), 'VARCHAR(512)')}"
        for col, dtype in df.dtypes.items()
    )
    
    # Re-create table to ensure fresh data
    drop_sql = f"DROP TABLE IF EXISTS {table_name};"
    create_sql = f"CREATE TABLE {table_name} ({cols_ddl});"

    rs_data_client.execute_statement(
        WorkgroupName=workgroup,
        Database=db,
        Sql=drop_sql,
    )
    time.sleep(1)
    
    rs_data_client.execute_statement(
        WorkgroupName=workgroup,
        Database=db,
        Sql=create_sql,
    )
    time.sleep(1)

    # Insert rows in batches of 100
    batch_size = 100
    inserted   = 0
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i : i + batch_size]
        rows  = []
        for _, row in batch.iterrows():
            vals = ", ".join(
                "NULL" if pd.isna(v) else f"'{str(v).replace(chr(39), chr(39)*2)}'"
                for v in row.values
            )
            rows.append(f"({vals})")
        insert_sql = f"INSERT INTO {table_name} VALUES {', '.join(rows)};"
        rs_data_client.execute_statement(
            WorkgroupName=workgroup,
            Database=db,
            Sql=insert_sql,
        )
        inserted += len(batch)
        print(f"  Inserted {inserted:,}/{len(df):,} rows...")

    print(f"'{table_name}' loaded successfully.")


def main():
    print("=" * 60)
    print(" REDSHIFT SERVERLESS DATA WAREHOUSE LOADER")
    print("=" * 60)

    rs_client      = boto3.client("redshift-serverless", region_name=REGION)
    rs_data_client = boto3.client("redshift-data",       region_name=REGION)
    storage_opts   = get_storage_options()

    endpoint, port = get_workgroup_endpoint(rs_client)
    if not endpoint:
        print("[ERROR] Workgroup is not available yet.")
        sys.exit(1)

    print(f"Redshift endpoint: {endpoint}:{port}")

    # Load Gold tables
    tables = [
        ("mart_features",   get_s3_path("features",      layer="gold")),
        ("backtest_report", get_s3_path("backtest_report", layer="gold")),
        ("recommendations", get_s3_path("recommendations", layer="gold")),
    ]

    for table_name, s3_path in tables:
        try:
            df = DeltaTable(s3_path, storage_options=storage_opts).to_pandas()
            # Trim mart_features to last 30 days for quick load
            if table_name == "mart_features" and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                cutoff = df["date"].max() - pd.Timedelta(days=30)
                df = df[df["date"] >= cutoff].copy()
            load_table_via_data_api(rs_data_client, WORKGROUP, DB_NAME, table_name, df)
        except Exception as e:
            print(f"[ERROR] Could not load {table_name}: {e}")

    print("\nRedshift Serverless data sync completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
