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
    "2_process_silver_gold",
    default_args=default_args,
    description="Processes raw Bronze data to Silver (cleaned/validated) and Gold (features)",
    schedule_interval=None, # Triggered after Ingestion completes, or run manually
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["processing", "silver", "gold"],
) as dag:

    process_silver = create_processing_task(
        task_id="bronze_to_silver",
        script_path="src/processing/bronze_to_silver.py",
        dag=dag
    )

    process_gold = create_processing_task(
        task_id="silver_to_gold",
        script_path="src/processing/silver_to_gold.py",
        dag=dag
    )

    process_silver >> process_gold
