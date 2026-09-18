"""
Optional Airflow DAG that runs the same pipeline as
`orchestrate.py`, but as separate tasks so you get per-task retries,
a dependency graph, and email alerting for free.

Drop this file into your Airflow DAGs folder. Update the `email`
address in default_args before deploying.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from etl import data_quality, extract_load_staging, transform_load_mart
from etl.utils import finish_batch, get_pg_connection, run_step, start_batch

default_args = {
    "owner": "data-eng",
    "depends_on_past": False,
    "email": ["you@example.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def _start_batch(**context):
    pg_conn = get_pg_connection()
    try:
        batch_id = start_batch(pg_conn)
        context["ti"].xcom_push(key="batch_id", value=batch_id)
    finally:
        pg_conn.close()


def _run_extract(**context):
    batch_id = context["ti"].xcom_pull(key="batch_id")
    pg_conn = get_pg_connection()
    try:
        run_step(
            pg_conn, batch_id, "extract_load_staging",
            extract_load_staging.load_all_staging_tables,
        )
    finally:
        pg_conn.close()


def _run_dims(**context):
    batch_id = context["ti"].xcom_pull(key="batch_id")
    pg_conn = get_pg_connection()
    try:
        run_step(
            pg_conn, batch_id, "transform_load_mart_dims",
            transform_load_mart.load_all_dims,
        )
    finally:
        pg_conn.close()


def _run_facts(**context):
    batch_id = context["ti"].xcom_pull(key="batch_id")
    pg_conn = get_pg_connection()
    try:
        run_step(
            pg_conn, batch_id, "transform_load_mart_facts",
            transform_load_mart.load_all_facts,
        )
    finally:
        pg_conn.close()


def _run_dq_and_finish(**context):
    batch_id = context["ti"].xcom_pull(key="batch_id")
    pg_conn = get_pg_connection()
    try:
        passed = data_quality.run_all_checks(pg_conn, batch_id)
        finish_batch(pg_conn, batch_id, "success" if passed else "failed")
        if not passed:
            raise RuntimeError(
                f"Critical DQ check failed for batch {batch_id} -- see etl.dq_results."
            )
    finally:
        pg_conn.close()


with DAG(
    dag_id="sakila_dw_pipeline",
    default_args=default_args,
    description="Sakila -> Postgres staging -> mart star schema",
    schedule_interval="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["sakila", "warehouse"],
) as dag:

    start = PythonOperator(task_id="start_batch", python_callable=_start_batch)
    extract = PythonOperator(task_id="extract_load_staging", python_callable=_run_extract)
    load_dims = PythonOperator(task_id="transform_load_mart_dims", python_callable=_run_dims)
    load_facts = PythonOperator(task_id="transform_load_mart_facts", python_callable=_run_facts)
    dq_and_finish = PythonOperator(task_id="data_quality_and_finish", python_callable=_run_dq_and_finish)

    start >> extract >> load_dims >> load_facts >> dq_and_finish
