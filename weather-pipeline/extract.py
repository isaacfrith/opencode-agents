"""Extract live weather forecasts from Open-Meteo and land them raw in DuckDB.

Appends one snapshot row per location per fetch. No transformation happens
here — all transformation is owned by the dbt models in dbt/.

Usage:
    .venv/bin/python extract.py           # respects the min-refetch interval
    .venv/bin/python extract.py --force   # always fetch
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import httpx
import typer

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "weather.duckdb"
LOCATIONS_CSV = ROOT / "dbt" / "seeds" / "locations.csv"

API_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_FIELDS = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "wind_speed_10m_max",
]
FORECAST_DAYS = 16  # Open-Meteo forecast API maximum
MIN_REFETCH_MINUTES = 15  # skip a location with a snapshot newer than this

app = typer.Typer(help="Extract live weather snapshots into the raw zone.")


def ensure_raw_table(con: duckdb.DuckDBPyConnection) -> None:
    """Create the raw zone if it doesn't exist. Append-only, no PK:
    the snapshot log keeps everything; the dbt layer picks the latest."""
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw.weather_responses (
            location_name TEXT,
            latitude      DOUBLE,
            longitude     DOUBLE,
            fetched_at    TIMESTAMP,
            request_url   TEXT,
            payload       JSON
        )
        """
    )


def load_locations() -> list[dict[str, str]]:
    with LOCATIONS_CSV.open(newline="") as f:
        return list(csv.DictReader(f))


def latest_snapshot_age_minutes(
    con: duckdb.DuckDBPyConnection, location_name: str
) -> float | None:
    row = con.execute(
        "SELECT max(fetched_at) FROM raw.weather_responses WHERE location_name = ?",
        [location_name],
    ).fetchone()
    if row is None or row[0] is None:
        return None
    last = row[0].replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds() / 60


@app.command()
def fetch(
    force: bool = typer.Option(
        False, "--force", help="Skip the minimum-refetch-interval guard."
    ),
) -> None:
    """Fetch a live forecast snapshot per location and append it to raw."""
    if not LOCATIONS_CSV.exists():
        typer.secho(f"No locations seed found at {LOCATIONS_CSV}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    locations = load_locations()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    ensure_raw_table(con)

    inserted = 0
    try:
        for loc in locations:
            name = loc["location_name"].strip()
            age = latest_snapshot_age_minutes(con, name)
            if age is not None and age < MIN_REFETCH_MINUTES and not force:
                typer.secho(
                    f"{name}: snapshot {age:.0f} min old (< {MIN_REFETCH_MINUTES}), "
                    "skipping — use --force",
                    fg=typer.colors.YELLOW,
                )
                continue

            params = {
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "timezone": loc["timezone"],
                "daily": ",".join(DAILY_FIELDS),
                "forecast_days": FORECAST_DAYS,
            }
            resp = httpx.get(API_URL, params=params, timeout=30.0)
            resp.raise_for_status()
            payload = resp.json()

            con.execute(
                """
                INSERT INTO raw.weather_responses
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    name,
                    float(loc["latitude"]),
                    float(loc["longitude"]),
                    datetime.now(timezone.utc).replace(tzinfo=None),
                    str(resp.url),
                    json.dumps(payload),
                ],
            )
            inserted += 1
            days = len(payload.get("daily", {}).get("time", []))
            typer.secho(
                f"{name}: snapshot landed ({days} forecast days)",
                fg=typer.colors.GREEN,
            )
    finally:
        con.close()

    typer.secho(
        f"Done — {inserted} snapshot(s) appended to raw.weather_responses.",
        fg=typer.colors.CYAN,
    )


if __name__ == "__main__":
    app()
