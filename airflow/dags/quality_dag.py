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
    "4_data_quality_checks",
    default_args=default_args,
    description="Dedicated quality assurance pipeline verifying table health across Bronze, Silver, and Gold layers",
    schedule_interval=None,
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["quality", "verification"],
) as dag:

    verify_bronze = create_processing_task(
        task_id="verify_bronze_layer",
        script_path="src/utils/verify_bronze.py",
        dag=dag
    )

    verify_silver = create_processing_task(
        task_id="verify_silver_layer",
        script_path="src/utils/verify_silver.py",
        dag=dag
    )

    verify_gold = create_processing_task(
        task_id="verify_gold_layer",
        script_path="src/utils/verify_gold.py",
        dag=dag
    )

    # Validate Bronze, then Silver, then Gold sequentially
    verify_bronze >> verify_silver >> verify_gold
