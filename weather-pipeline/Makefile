VENV := .venv
PY := $(VENV)/bin/python
DBT := $(VENV)/bin/dbt
PY3 ?= python3.11

.PHONY: setup extract build all verify

setup:
	$(PY3) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e .

extract:
	$(PY) extract.py

build:
	cd dbt && ../$(DBT) deps
	cd dbt && ../$(DBT) build

verify:
	$(PY) -c "import duckdb; con = duckdb.connect('data/weather.duckdb'); print(con.sql('SELECT * FROM fct_weather__daily ORDER BY forecast_date'))"

all: extract build verify
