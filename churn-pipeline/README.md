# churn-pipeline

A local analytics platform that lands bank customer records in **DuckDB**,
transforms them with **dbt**, trains an **XGBoost** churn model tracked in
**MLflow**, and serves predictions through a **FastAPI** scorer with a small web
form. Models run in **Docker** (MLflow + API).

## Layout

```
churn-pipeline/
├── extract.py        # Kaggle → raw.customers in DuckDB
├── train.py          # mart → tuned XGBoost pipeline → MLflow (registered version)
├── promote.py        # point @champion at a version
├── score.py          # @champion → ml.churn_predictions
├── churnlib/         # feature contract + config + registry helpers
├── dbt/              # stg_customers (view) → fct_customer_churn_features (table)
├── api/              # FastAPI app + form  (loads @champion, stateless)
├── Dockerfile        # python:3.11-slim + uv
├── docker-compose.yml# mlflow + api
├── GLOSSARY.md       # domain vocabulary
└── docs/adr/         # decision records
```

## Quickstart (host pipeline + Docker services)

```bash
make setup          # uv sync
make extract        # download dataset → raw.customers
make build          # dbt deps + dbt build → feature mart
make compose-up     # start MLflow (:5001) and the API (:8000)
make train          # tune + log + register a model version
make promote        # point @champion at the newest version
make score          # write ml.churn_predictions
make verify         # summarise the scored population
```

Then open <http://localhost:8000> for the form and <http://localhost:8000/docs>
for the API. MLflow is at <http://127.0.0.1:5001>.

`make all` runs `extract → build → train → promote → score → verify`.

## Host-only (no Docker)

Run MLflow on the host instead of compose:

```bash
make mlflow         # mlflow server on :5001 (sqlite + ./mlruns)
make serve          # FastAPI on :8000
```

The batch scripts use `MLFLOW_TRACKING_URI` (default `http://127.0.0.1:5001`).

## Notes

- Data is **not committed**; `data/` is gitignored. `extract.py` prefers
  `kagglehub` and falls back to Kaggle's public download endpoint.
- The model artifact is a full scikit-learn `Pipeline` (encoder + XGBoost), so
  training and serving share exactly one feature path — see
  `docs/adr/0001-feature-engineering-in-sklearn-pipeline.md`.
- The API serves whichever version carries the `@champion` alias — see
  `docs/adr/0002-serving-via-mlflow-champion-alias.md`.
