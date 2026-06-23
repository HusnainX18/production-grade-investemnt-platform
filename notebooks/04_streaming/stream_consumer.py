"""
Databricks Notebook: Kinesis Streaming Consumer.
Paste this code into a Databricks Notebook cell.

Reads live market data from AWS Kinesis using Spark Structured Streaming,
parses the JSON payload, and appends records to a S3 Delta table.
"""

from pyspark.sql.functions import from_json, col, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

# ── Configuration ─────────────────────────────────────────────────────────────
AWS_REGION      = "us-east-1"
STREAM_NAME     = "investment-platform-market-stream"
S3_BUCKET       = "investment-platform-husnain"
S3_OUTPUT_PATH  = f"s3://{S3_BUCKET}/streaming/live_market_stream"
CHECKPOINT_PATH = f"s3://{S3_BUCKET}/checkpoints/live_market_stream"

# Recommended: configure IAM roles on the Databricks instance profile instead
# of storing credentials here.
AWS_ACCESS_KEY = dbutils.secrets.get(scope="aws", key="access_key")
AWS_SECRET_KEY = dbutils.secrets.get(scope="aws", key="secret_key")

# ── Read from Kinesis ─────────────────────────────────────────────────────────
kinesis_df = (
    spark.readStream
    .format("kinesis")
    .option("streamName", STREAM_NAME)
    .option("region", AWS_REGION)
    .option("initialPosition", "trim_horizon")
    .option("awsAccessKey", AWS_ACCESS_KEY)
    .option("awsSecretKey", AWS_SECRET_KEY)
    .load()
)

# ── Parse JSON payload ────────────────────────────────────────────────────────
schema = StructType([
    StructField("symbol",    StringType(), True),
    StructField("price",     DoubleType(), True),
    StructField("size",      DoubleType(), True),
    StructField("timestamp", StringType(), True),
    StructField("source",    StringType(), True),
])

parsed_df = (
    kinesis_df
    .selectExpr("CAST(data AS STRING) as json_payload")
    .select(from_json("json_payload", schema).alias("data"))
    .select("data.*")
    .withColumn("ingestion_timestamp", current_timestamp())
)

# ── Write to S3 Delta Table ───────────────────────────────────────────────────
query = (
    parsed_df.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", CHECKPOINT_PATH)
    .trigger(availableNow=True)
    .start(S3_OUTPUT_PATH)
)

# Uncomment to display stream output inline:
# display(parsed_df)
