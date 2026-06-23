"""
S3 and Delta Lake storage helper utility.
Centralises AWS configuration and Delta Lake write operations.
"""

import os
import yaml
from deltalake import write_deltalake

def get_storage_options():
    """
    Read AWS credentials from the environment and return storage options for deltalake.
    """
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "us-east-1")
    
    if not aws_access_key or not aws_secret_key:
        raise ValueError(
            "AWS credentials AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in the environment."
        )
        
    return {
        "AWS_ACCESS_KEY_ID": aws_access_key,
        "AWS_SECRET_ACCESS_KEY": aws_secret_key,
        "AWS_REGION": aws_region,
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }

def get_s3_path(table_name, layer="bronze"):
    """
    Read bucket name from configuration and build the target S3 path for the specified layer.
    """
    config_path = "config/config.yaml"
    if not os.path.exists(config_path):
        # Fallback if running from tests directory
        config_path = os.path.join(os.path.dirname(__file__), "../../config/config.yaml")
        
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    bucket = config["aws"]["s3_bucket"]
    return f"s3://{bucket}/{layer}/{table_name}"

def write_bronze_delta(df, table_name, mode="overwrite"):
    """
    Write a Pandas DataFrame directly to S3 as a Bronze Delta table.
    """
    storage_options = get_storage_options()
    s3_path = get_s3_path(table_name, layer="bronze")
    
    write_deltalake(
        s3_path,
        df,
        storage_options=storage_options,
        mode=mode,
        schema_mode="overwrite" if mode == "overwrite" else None,
    )

def write_silver_delta(df, table_name, mode="overwrite"):
    """
    Write a Pandas DataFrame directly to S3 as a Silver Delta table.
    """
    storage_options = get_storage_options()
    s3_path = get_s3_path(table_name, layer="silver")
    
    write_deltalake(
        s3_path,
        df,
        storage_options=storage_options,
        mode=mode,
        schema_mode="overwrite" if mode == "overwrite" else None,
    )
