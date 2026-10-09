"""The model's feature contract: which columns, and how they are encoded.

This is the single source of truth for feature shaping (see
``docs/adr/0001-feature-engineering-in-sklearn-pipeline.md``). Training and
serving both build inputs through :func:`build_pipeline` / ``FEATURE_COLUMNS``,
so the two paths cannot diverge.

Column names are snake_case because that is how dbt stages them out of
``raw.customers``.
"""

from __future__ import annotations

from typing import Any

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

ID_COLUMN = "customer_id"
TARGET_COLUMN = "exited"

CATEGORICAL_COLUMNS = ["geography", "gender"]
NUMERIC_COLUMNS = [
    "credit_score",
    "age",
    "tenure",
    "balance",
    "num_of_products",
    "has_cr_card",
    "is_active_member",
    "estimated_salary",
]
FEATURE_COLUMNS = [
    "credit_score",
    "geography",
    "gender",
    "age",
    "tenure",
    "balance",
    "num_of_products",
    "has_cr_card",
    "is_active_member",
    "estimated_salary",
]

# Sensible XGBoost defaults; the search overrides most of these.
XGB_DEFAULTS: dict[str, Any] = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.1,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "min_child_weight": 1,
    "eval_metric": "logloss",
    "tree_method": "hist",
    "n_jobs": 4,
}


def build_estimator(scale_pos_weight: float, **params: Any) -> XGBClassifier:
    """An XGBoost classifier with ``scale_pos_weight`` for the class imbalance."""
    settings = {**XGB_DEFAULTS, **params}
    return XGBClassifier(scale_pos_weight=scale_pos_weight, **settings)


def build_pipeline(scale_pos_weight: float = 1.0, **params: Any) -> Pipeline:
    """The persisted artifact: one-hot categoricals, passthrough numerics, XGBoost.

    No imputer (the data has no nulls) and no scaler (trees are scale-invariant).
    """
    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLUMNS),
        ],
        remainder="passthrough",
    )
    return Pipeline([("pre", pre), ("model", build_estimator(scale_pos_weight, **params))])
