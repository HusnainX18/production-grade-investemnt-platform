from datetime import datetime, timedelta
from airflow import DAG
from utils import create_dbt_task

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "3_transform_dbt",
    default_args=default_args,
    description="Orchestrates dbt SQL transformations (run + test) on AWS Databricks",
    schedule_interval=None, # Triggered after Silver/Gold completes
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["dbt", "databricks", "transformation"],
) as dag:

    dbt_run = create_dbt_task(
        task_id="dbt_run",
        dbt_command="run",
        dag=dag
    )

    dbt_test = create_dbt_task(
        task_id="dbt_test",
        dbt_command="test",
        dag=dag
    )

    dbt_run >> dbt_test
