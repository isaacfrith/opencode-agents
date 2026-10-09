"""Score the whole customer population with the ``@champion`` model.

Loads ``@champion`` from the MLflow registry and writes ``ml.churn_predictions``
for every customer in the dbt feature mart.

Usage:
    uv run python score.py
"""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import mlflow
import mlflow.sklearn
import typer

from churnlib import config, features, registry

app = typer.Typer(help="Score the population with @champion.")


@app.command()
def main() -> None:
    version = registry.champion()
    if version is None:
        typer.secho(
            "No @champion model found. Run `make train` then `make promote`.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    threshold = float(version.tags.get(config.THRESHOLD_TAG, config.DEFAULT_THRESHOLD))

    mlflow.set_tracking_uri(config.tracking_uri())
    model = mlflow.sklearn.load_model(registry.champion_uri())

    con = duckdb.connect(str(config.DB_PATH))
    try:
        df = con.execute(f"SELECT * FROM {config.MART_TABLE}").df()
        scores = model.predict_proba(df[features.FEATURE_COLUMNS])[:, 1]

        out = df[[features.ID_COLUMN]].copy()
        out["churn_score"] = scores
        out["predicted_churn"] = scores >= threshold
        out["threshold"] = threshold
        out["model_version"] = int(version.version)
        out["scored_at"] = datetime.now(timezone.utc).replace(tzinfo=None)

        con.execute(f"CREATE SCHEMA IF NOT EXISTS {config.PREDICTIONS_SCHEMA}")
        con.register("preds", out)
        con.execute(
            f"CREATE OR REPLACE TABLE "
            f"{config.PREDICTIONS_SCHEMA}.{config.PREDICTIONS_TABLE} AS "
            "SELECT * FROM preds"
        )
        flagged = int(out["predicted_churn"].sum())
        total = len(out)
    finally:
        con.close()

    typer.secho(
        f"Scored {total:,} customers with {config.REGISTERED_MODEL} "
        f"v{version.version} (threshold={threshold:.3f}); flagged {flagged:,}.",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":
    app()
