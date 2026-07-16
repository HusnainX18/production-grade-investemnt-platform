"""
Amazon Redshift Serverless loader.
Creates a Redshift Serverless namespace + workgroup, then loads the
mart_features, backtest_report and recommendations Gold tables from S3.
Run once for demo purposes. Remember to delete the workgroup after the demo.
"""

import os
import sys
import time
import boto3
import pandas as pd
from deltalake import DeltaTable
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.utils.s3_helper import get_s3_path, get_storage_options

load_dotenv()

REGION          = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
NAMESPACE       = "marketpulse-ns"
WORKGROUP       = "marketpulse-wg"
DB_NAME         = "marketpulse"
ADMIN_USER      = "admin"
ADMIN_PASSWORD  = "MarketPulse2026!"   # min 8 chars, upper+lower+digit
BUCKET          = "marketpulse-datalake-husnain"


def get_or_create_namespace(rs_client):
    """Create Redshift Serverless namespace if it doesn't exist."""
    try:
        ns = rs_client.get_namespace(namespaceName=NAMESPACE)
        print(f"Namespace '{NAMESPACE}' already exists.")
        return ns["namespace"]["namespaceArn"]
    except rs_client.exceptions.ResourceNotFoundException:
        print(f"Creating namespace '{NAMESPACE}'...")
        ns = rs_client.create_namespace(
            namespaceName=NAMESPACE,
            adminUsername=ADMIN_USER,
            adminUserPassword=ADMIN_PASSWORD,
            dbName=DB_NAME,
        )
        print("Namespace created.")
        return ns["namespace"]["namespaceArn"]


def setup_vpc_subnets():
    """Ensure we have at least 3 subnets in different AZs for Redshift Serverless."""
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc_id = "vpc-068c381f7ea7aa406"
    rt_id = "rtb-0211c94bf2a17e88d"
    
    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    subnet_ids = [s["SubnetId"] for s in subnets]
    azs = [s["AvailabilityZone"] for s in subnets]
    
    required_azs = ["us-east-1b", "us-east-1c"]
    cidr_blocks = ["10.0.2.0/24", "10.0.3.0/24"]
    
    for az, cidr in zip(required_azs, cidr_blocks):
        if az not in azs:
            print(f"Creating subnet in {az} ({cidr})...")
            try:
                new_subnet = ec2.create_subnet(
                    VpcId=vpc_id,
                    CidrBlock=cidr,
                    AvailabilityZone=az
                )["Subnet"]
                new_subnet_id = new_subnet["SubnetId"]
                subnet_ids.append(new_subnet_id)
                
                # Associate with public route table
                ec2.associate_route_table(
                    SubnetId=new_subnet_id,
                    RouteTableId=rt_id
                )
                print(f"  Created and associated {new_subnet_id}")
            except Exception as e:
                print(f"  Could not create subnet in {az}: {e}")
                
    return subnet_ids


def get_or_create_workgroup(rs_client):
    """Create Redshift Serverless workgroup if it doesn't exist."""
    try:
        wg = rs_client.get_workgroup(workgroupName=WORKGROUP)
        print(f"Workgroup '{WORKGROUP}' already exists.")
        endpoint = wg["workgroup"]["endpoint"]["address"]
        port     = wg["workgroup"]["endpoint"]["port"]
        return endpoint, port
    except rs_client.exceptions.ResourceNotFoundException:
        print("Setting up required VPC subnets for Redshift Serverless...")
        subnet_ids = setup_vpc_subnets()
        
        print(f"Creating workgroup '{WORKGROUP}' with subnets {subnet_ids}...")
        rs_client.create_workgroup(
            workgroupName=WORKGROUP,
            namespaceName=NAMESPACE,
            baseCapacity=8,           # 8 RPU minimum for Serverless
            publiclyAccessible=True,
            subnetIds=subnet_ids,
        )

    # Wait for workgroup to become AVAILABLE
    print("Waiting for workgroup to become available (1-3 minutes)...")
    while True:
        wg = rs_client.get_workgroup(workgroupName=WORKGROUP)
        status = wg["workgroup"]["status"]
        print(f"  Workgroup status: {status}")
        if status == "AVAILABLE":
            endpoint = wg["workgroup"]["endpoint"]["address"]
            port     = wg["workgroup"]["endpoint"]["port"]
            return endpoint, port
        time.sleep(20)


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
    create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_ddl});"

    rs_data_client.execute_statement(
        WorkgroupName=workgroup,
        Database=db,
        Sql=create_sql,
    )

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
    print(" REDSHIFT SERVERLESS SETUP & DATA LOADER")
    print("=" * 60)

    rs_client      = boto3.client("redshift-serverless", region_name=REGION)
    rs_data_client = boto3.client("redshift-data",       region_name=REGION)
    storage_opts   = get_storage_options()

    get_or_create_namespace(rs_client)
    endpoint, port = get_or_create_workgroup(rs_client)
    print(f"\nRedshift endpoint: {endpoint}:{port}")

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

    print("\n" + "=" * 60)
    print("Redshift Serverless setup complete.")
    print(f"Endpoint : {endpoint}")
    print(f"Port     : {port}")
    print(f"Database : {DB_NAME}")
    print(f"User     : {ADMIN_USER}")
    print(f"Password : {ADMIN_PASSWORD}")
    print("\nConnect via AWS Query Editor v2:")
    print(f"https://console.aws.amazon.com/sqlworkbench/home?region={REGION}")
    print("\nIMPORTANT: Delete the workgroup after demo to avoid charges.")
    print(f"  aws redshift-serverless delete-workgroup --workgroup-name {WORKGROUP} --region {REGION}")
    print(f"  aws redshift-serverless delete-namespace --namespace-name {NAMESPACE} --region {REGION}")
    print("=" * 60)


if __name__ == "__main__":
    main()
