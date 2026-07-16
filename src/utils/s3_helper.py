"""
AWS S3 and Delta Lake storage helper utility.
Centralises AWS configuration and Delta Lake write operations.
"""

import os
import yaml
from pathlib import Path
from typing import Literal
import pandas as pd
from deltalake import write_deltalake

def get_storage_options():
    """
    Read AWS credentials from the environment and return storage options for deltalake.
    """
    if os.getenv("LOCAL_DEV", "false").lower() == "true":
        return {}
        
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    # Try to load standard AWS CLI environment variables first
    # If not set, let delta-rs rely on the default provider chain (which reads ~/.aws/credentials)
    opts = {}
    if aws_key:
        opts["aws_access_key_id"] = aws_key
    if aws_secret:
        opts["aws_secret_access_key"] = aws_secret
    if aws_region:
        opts["aws_region"] = aws_region
        
    return opts

def get_s3_path(table_name, layer="bronze"):
    """
    Build the target AWS S3 path.
    
    Returns:
        s3://<bucket>/<layer>/<table_name>
    """
    if os.getenv("LOCAL_DEV", "false").lower() == "true":
        project_root = Path(__file__).resolve().parents[2]
        return str(project_root / "data" / layer / table_name).replace("\\", "/")
        
    bucket = os.getenv("S3_BUCKET", "marketpulse-datalake-husnain")
    return f"s3://{bucket}/{layer}/{table_name}"

def write_bronze_delta(df: pd.DataFrame, table_name: str, mode: Literal["append", "overwrite", "error", "ignore"] = "overwrite") -> None:
    """
    Write a Pandas DataFrame directly to S3 as a Bronze Delta table.
    """
    storage_options = get_storage_options()
    path = get_s3_path(table_name, layer="bronze")
    
    write_deltalake(
        path,
        df,
        storage_options=storage_options,
        mode=mode,
        schema_mode="overwrite" if mode == "overwrite" else None,
    )

def write_silver_delta(df: pd.DataFrame, table_name: str, mode: Literal["append", "overwrite", "error", "ignore"] = "overwrite") -> None:
    """
    Write a Pandas DataFrame directly to S3 as a Silver Delta table.
    """
    storage_options = get_storage_options()
    path = get_s3_path(table_name, layer="silver")
    
    write_deltalake(
        path,
        df,
        storage_options=storage_options,
        mode=mode,
        schema_mode="overwrite" if mode == "overwrite" else None,
    )

def write_gold_delta(df: pd.DataFrame, table_name: str, mode: Literal["append", "overwrite", "error", "ignore"] = "overwrite") -> None:
    """
    Write a Pandas DataFrame directly to S3 as a Gold Delta table.
    """
    storage_options = get_storage_options()
    path = get_s3_path(table_name, layer="gold")
    
    write_deltalake(
        path,
        df,
        storage_options=storage_options,
        mode=mode,
        schema_mode="overwrite" if mode == "overwrite" else None,
    )

