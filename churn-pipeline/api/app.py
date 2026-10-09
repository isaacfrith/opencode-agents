"""FastAPI scorer.

Loads the ``@champion`` model from MLflow at startup and exposes a
single-customer prediction endpoint plus a minimal web form. The service is
stateless: it never touches DuckDB.

Run locally:
    uv run python -m uvicorn api.app:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from api.schemas import CustomerInput, Prediction
from churnlib import config, features, registry

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Populated at startup; the model is loaded once and reused per request.
STATE: dict[str, Any] = {"model": None, "version": None, "threshold": None, "error": None}


def load_champion() -> None:
    try:
        version = registry.champion()
        if version is None:
            raise RuntimeError(f"no @{config.CHAMPION_ALIAS} model registered")
        mlflow.set_tracking_uri(config.tracking_uri())
        STATE["model"] = mlflow.sklearn.load_model(registry.champion_uri())
        STATE["version"] = int(version.version)
        STATE["threshold"] = float(
            version.tags.get(config.THRESHOLD_TAG, config.DEFAULT_THRESHOLD)
        )
        STATE["error"] = None
    except Exception as exc:  # keep the service up; /health reports the problem
        STATE["model"] = None
        STATE["error"] = str(exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_champion()
    yield


app = FastAPI(title="Churn scoring API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok" if STATE["model"] is not None else "model_unavailable",
        "model_version": STATE["version"],
        "error": STATE["error"],
    }


@app.get("/model")
def model_info() -> dict[str, Any]:
    return {
        "registered_model": config.REGISTERED_MODEL,
        "alias": config.CHAMPION_ALIAS,
        "version": STATE["version"],
        "threshold": STATE["threshold"],
    }


@app.post("/predict", response_model=Prediction)
def predict(customer: CustomerInput) -> Prediction:
    if STATE["model"] is None:
        raise HTTPException(
            status_code=503, detail=f"Model unavailable: {STATE['error']}"
        )
    row = pd.DataFrame([customer.model_dump(mode="json")])[features.FEATURE_COLUMNS]
    score = float(STATE["model"].predict_proba(row)[0, 1])
    return Prediction(
        churn_score=score,
        predicted_churn=score >= STATE["threshold"],
        threshold=STATE["threshold"],
        model_version=STATE["version"],
    )


@app.get("/", response_class=HTMLResponse)
def form(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(request, "index.html")
