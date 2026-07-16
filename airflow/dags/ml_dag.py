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
    "5_ml_nightly_retrain",
    default_args=default_args,
    description="Nightly ML pipeline running placeholder model training and evaluation tasks",
    schedule_interval="0 1 * * *", # Runs nightly at 1 AM
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["ml", "training", "retrain"],
) as dag:

    ml_retrain = create_processing_task(
        task_id="ml_model_retrain",
        script_path="src/ml/train.py",
        dag=dag
    )

    backtest_eval = create_processing_task(
        task_id="backtest_evaluation",
        script_path="src/backtesting/backtester.py",
        dag=dag
    )

    gen_recs = create_processing_task(
        task_id="generate_recommendations",
        script_path="src/recommendation/engine.py",
        dag=dag
    )

    load_dw = create_processing_task(
        task_id="load_data_warehouse",
        script_path="src/analytics/AWS_sql_loader.py",
        dag=dag
    )

    ml_retrain >> backtest_eval >> gen_recs >> load_dw
