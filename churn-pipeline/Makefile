UV := uv
PROFILES := --profiles-dir .

.PHONY: setup extract build train promote score serve mlflow compose-up compose-down verify all

## Install the uv-managed environment (creates .venv, writes uv.lock).
setup:
	uv sync

## Download the Kaggle dataset and land it in DuckDB (raw.customers).
extract:
	uv run python extract.py

## Build the dbt staging view and feature mart into DuckDB.
build:
	cd dbt && uv run dbt deps $(PROFILES)
	cd dbt && uv run dbt build $(PROFILES)

## Train, tune, and log the model to MLflow; register a new version.
train:
	uv run python train.py

## Promote a model version to the @champion alias (VERSION=latest by default).
promote:
	uv run python promote.py $(if $(VERSION),--version $(VERSION),)

## Load @champion and write ml.churn_predictions for the whole population.
score:
	uv run python score.py

## Run the FastAPI scorer locally against the host MLflow server.
serve:
	uv run python -m uvicorn api.app:app --reload --port 8000

## Run a local MLflow tracking server on :5001 (host, no Docker; 5000 is taken
## by macOS AirPlay Receiver).
mlflow:
	uv run mlflow server --host 127.0.0.1 --port 5001 \
		--backend-store-uri sqlite:///mlruns/mlflow.db \
		--artifacts-destination ./mlruns/artifacts \
		--serve-artifacts

## Start MLflow + API via Docker Compose.
compose-up:
	docker compose up --build -d

compose-down:
	docker compose down

## Inspect the scored population.
verify:
	uv run python -c "import duckdb; c=duckdb.connect('data/churn.duckdb'); print(c.sql('select count(*) as scored, round(avg(churn_score),3) as mean_score, sum(predicted_churn::int) as flagged from ml.churn_predictions'))"

all: extract build train promote score verify
