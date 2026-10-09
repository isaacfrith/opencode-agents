"""Download the Kaggle bank-churn dataset and land it in DuckDB.

Fetches the canonical 14-column dataset (the one that actually contains the
``Exited`` label) via ``kagglehub`` and writes it to ``raw.customers``. No
transformation happens here — all of that is owned by the dbt models in ``dbt/``.

The data is never committed; ``data/`` is gitignored.

Usage:
    uv run python extract.py
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import duckdb
import httpx
import pandas as pd
import typer

from churnlib import config

app = typer.Typer(help="Land the raw bank-churn dataset into DuckDB.")


def _download_via_kagglehub() -> Path:
    import kagglehub

    root = Path(kagglehub.dataset_download(config.KAGGLE_DATASET))
    csv = next(root.rglob("*.csv"), None)
    if csv is None:
        raise FileNotFoundError(f"No CSV found in kagglehub download at {root}")
    return csv


def _download_via_public_api() -> Path:
    """Fallback that needs no credentials: Kaggle's public download endpoint."""
    url = f"https://www.kaggle.com/api/v1/datasets/download/{config.KAGGLE_DATASET}"
    tmp = Path(tempfile.mkdtemp(prefix="churn-kaggle-"))
    archive = tmp / "data.zip"
    resp = httpx.get(url, follow_redirects=True, timeout=60.0)
    resp.raise_for_status()
    archive.write_bytes(resp.content)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(tmp)
    csv = next(tmp.rglob("*.csv"), None)
    if csv is None:
        raise FileNotFoundError("No CSV found in the downloaded archive.")
    return csv


def fetch() -> pd.DataFrame:
    """Return the raw dataset as a DataFrame, preferring kagglehub."""
    try:
        csv = _download_via_kagglehub()
    except Exception as exc:
        typer.secho(
            f"kagglehub unavailable ({exc}); using the public download endpoint.",
            fg=typer.colors.YELLOW,
        )
        csv = _download_via_public_api()
    return pd.read_csv(csv)


@app.command()
def main() -> None:
    typer.secho(f"Downloading {config.KAGGLE_DATASET} ...", fg=typer.colors.CYAN)
    df = fetch()

    if "Exited" not in df.columns:
        typer.secho(
            "Downloaded file has no 'Exited' column — wrong dataset.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DB_PATH))
    try:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {config.RAW_SCHEMA}")
        con.register("df", df)
        con.execute(
            f"CREATE OR REPLACE TABLE {config.RAW_SCHEMA}.{config.RAW_TABLE} AS "
            "SELECT * FROM df"
        )
        rows = con.execute(
            f"SELECT count(*) FROM {config.RAW_SCHEMA}.{config.RAW_TABLE}"
        ).fetchone()[0]
    finally:
        con.close()

    churn_rate = df["Exited"].mean()
    typer.secho(
        f"Landed {rows:,} rows x {df.shape[1]} cols into "
        f"{config.RAW_SCHEMA}.{config.RAW_TABLE} "
        f"(churn rate {churn_rate:.1%}).",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":
    app()
