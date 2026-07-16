from datetime import datetime, timedelta
from airflow import DAG
from utils import create_processing_task

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "1_ingest_bronze",
    default_args=default_args,
    description="Batch Ingestion pipeline to load historical/daily raw data into S3 Bronze layer",
    schedule_interval="0 6 * * *", # Daily at 6 AM
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["ingestion", "bronze"],
) as dag:

    ingest_stocks = create_processing_task(
        task_id="ingest_stocks",
        script_path="src/ingestion/ingest_stocks.py",
        dag=dag
    )

    ingest_crypto = create_processing_task(
        task_id="ingest_crypto",
        script_path="src/ingestion/ingest_crypto.py",
        dag=dag
    )

    ingest_macro = create_processing_task(
        task_id="ingest_macro",
        script_path="src/ingestion/ingest_macro.py",
        dag=dag
    )

    ingest_news = create_processing_task(
        task_id="ingest_news",
        script_path="src/ingestion/ingest_news.py",
        dag=dag
    )

    # All ingestions run in parallel
    [ingest_stocks, ingest_crypto, ingest_macro, ingest_news]
