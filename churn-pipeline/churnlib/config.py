"""Shared configuration: filesystem paths and the MLflow naming contract."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "churn.duckdb"

# Raw landing zone (written by extract.py) and dbt's physical schema. dbt-duckdb
# writes models to the `main` schema, mirroring weather-pipeline.
RAW_SCHEMA = "raw"
RAW_TABLE = "customers"
MART_TABLE = "fct_customer_churn_features"

# Model output (written by score.py).
PREDICTIONS_SCHEMA = "ml"
PREDICTIONS_TABLE = "churn_predictions"

# MLflow contract — see docs/adr/0002-serving-via-mlflow-champion-alias.md
EXPERIMENT = "churn"
REGISTERED_MODEL = "churn_xgboost"
CHAMPION_ALIAS = "champion"
THRESHOLD_TAG = "decision_threshold"
DEFAULT_THRESHOLD = 0.5

# Source dataset: canonical 14-column bank churn (has the `Exited` label).
KAGGLE_DATASET = "shantanudhakadd/bank-customer-churn-prediction"
KAGGLE_CSV = "Churn_Modelling.csv"


def tracking_uri() -> str:
    """MLflow tracking URI.

    Compose sets ``MLFLOW_TRACKING_URI`` to the ``mlflow`` service; running
    locally it defaults to a tracking server on ``127.0.0.1:5001``.
    """
    return os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")
