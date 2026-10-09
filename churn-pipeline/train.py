"""Train and tune the churn model, log it to MLflow, register a version.

Reads the dbt feature mart, tunes an XGBoost pipeline with a stratified
RandomizedSearchCV, chooses a decision threshold on the holdout set, logs
params / metrics / the full pipeline to MLflow, and registers a new model
version tagged with that threshold.

Usage:
    uv run python train.py
    uv run python train.py --n-iter 30
"""

from __future__ import annotations

import duckdb
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import typer
from mlflow.models import infer_signature
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, train_test_split

from churnlib import config, features, registry

app = typer.Typer(help="Train, tune and register the churn model.")

PARAM_DISTRIBUTIONS = {
    "model__n_estimators": [200, 300, 400, 600],
    "model__max_depth": [3, 4, 5, 6],
    "model__learning_rate": [0.03, 0.05, 0.1, 0.2],
    "model__subsample": [0.7, 0.8, 0.9, 1.0],
    "model__colsample_bytree": [0.7, 0.8, 0.9, 1.0],
    "model__min_child_weight": [1, 3, 5],
}


def load_features() -> pd.DataFrame:
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    try:
        return con.execute(f"SELECT * FROM {config.MART_TABLE}").df()
    finally:
        con.close()


def best_threshold(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Threshold that maximises F1 on the holdout predictions."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_score)
    f1 = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros_like(precision),
        where=(precision + recall) > 0,
    )
    return float(thresholds[int(np.argmax(f1[:-1]))])


@app.command()
def main(
    n_iter: int = typer.Option(20, help="RandomizedSearchCV iterations."),
    seed: int = typer.Option(42, help="Random seed."),
) -> None:
    df = load_features()
    X = df[features.FEATURE_COLUMNS]
    y = df[features.TARGET_COLUMN].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=seed
    )

    positives = int(y_train.sum())
    negatives = int(len(y_train) - positives)
    scale_pos_weight = negatives / positives
    typer.echo(
        f"train={len(X_train):,} test={len(X_test):,} "
        f"scale_pos_weight={scale_pos_weight:.2f}"
    )

    search = RandomizedSearchCV(
        features.build_pipeline(scale_pos_weight=scale_pos_weight),
        param_distributions=PARAM_DISTRIBUTIONS,
        n_iter=n_iter,
        scoring="roc_auc",
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=seed),
        random_state=seed,
        n_jobs=-1,
        refit=True,
    )
    search.fit(X_train, y_train)
    model = search.best_estimator_
    typer.echo(f"best CV ROC-AUC = {search.best_score_:.4f}")

    y_score = model.predict_proba(X_test)[:, 1]
    threshold = best_threshold(y_test.to_numpy(), y_score)
    y_pred = (y_score >= threshold).astype(int)

    metrics = {
        "roc_auc": roc_auc_score(y_test, y_score),
        "pr_auc": average_precision_score(y_test, y_score),
        "threshold": threshold,
        "f1": f1_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "cv_roc_auc": search.best_score_,
    }

    mlflow.set_tracking_uri(config.tracking_uri())
    mlflow.set_experiment(config.EXPERIMENT)
    with mlflow.start_run() as run:
        mlflow.log_params(
            {**search.best_params_, "scale_pos_weight": round(scale_pos_weight, 4)}
        )
        mlflow.log_metrics({k: float(v) for k, v in metrics.items()})
        mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            signature=infer_signature(X_train, model.predict_proba(X_train)),
            input_example=X_train.head(3),
        )
        registered = mlflow.register_model(
            f"runs:/{run.info.run_id}/model", config.REGISTERED_MODEL
        )
        registry.client().set_model_version_tag(
            config.REGISTERED_MODEL,
            registered.version,
            config.THRESHOLD_TAG,
            str(threshold),
        )

    typer.secho(
        f"Run {run.info.run_id[:8]} · registered {config.REGISTERED_MODEL} "
        f"v{registered.version} · ROC-AUC={metrics['roc_auc']:.4f} "
        f"PR-AUC={metrics['pr_auc']:.4f} threshold={threshold:.3f}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Promote it with: make promote VERSION={registered.version}")


if __name__ == "__main__":
    app()
