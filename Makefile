.PHONY: help install ingest load transform test dashboard lint

help:
	@echo "Targets:"
	@echo "  install    Install Python dependencies"
	@echo "  ingest     Run the ingestion layer (writes raw JSON to data/raw/)"
	@echo "  load       Load raw JSON into Postgres"
	@echo "  transform  Run dbt build (models + tests)"
	@echo "  test       Run the pytest suite"
	@echo "  dashboard  Launch the Streamlit dashboard"
	@echo "  lint       Run ruff"

install:
	pip install -r requirements.txt

ingest:
	python -m ingestion.run_ingestion

load:
	python -m db.load_raw

transform:
	cd dbt_project && dbt build

test:
	pytest

dashboard:
	streamlit run dashboard/app.py

lint:
	ruff check .
