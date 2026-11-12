from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

from airflow import DAG
from airflow.operators.python import PythonOperator

PROJECT = Path("/opt/airflow/project")


def выполнить_анализ():
    subprocess.run(
        [sys.executable, str(PROJECT / "src" / "pipeline.py"),
         "--input", str(PROJECT / "data" / "DZ_user_actions.csv"),
         "--output", str(PROJECT / "output")],
        check=True,
    )


with DAG(
    dag_id="analitika_magazina",
    description="Загрузка CSV, расчёт метрик, Excel и Plotly-отчёт",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args={"owner": "student", "retries": 1,
                  "retry_delay": timedelta(minutes=5)},
    tags=["учебный-проект", "аналитика"],
) as dag:
    выполнить = PythonOperator(
        task_id="обновить_базу_и_отчёты",
        python_callable=выполнить_анализ,
    )
