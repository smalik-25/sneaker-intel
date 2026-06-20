.PHONY: help install db-up db-down db-init ingest load transform test dashboard lint

help:
	@echo "Targets:"
	@echo "  install    Install Python dependencies"
	@echo "  db-up      Start the local Postgres container (docker compose)"
	@echo "  db-down    Stop the local Postgres container"
	@echo "  db-init    Apply schema.sql then seeds.sql to the database"
	@echo "  ingest     Run the ingestion layer (writes raw JSON to data/raw/)"
	@echo "  load       Load raw JSON into Postgres"
	@echo "  transform  Run dbt build (models + tests)"
	@echo "  test       Run the pytest suite"
	@echo "  dashboard  Launch the Streamlit dashboard"
	@echo "  lint       Run ruff"

install:
	pip install -r requirements.txt

db-up:
	docker compose up -d

db-down:
	docker compose down

# Runs psql *inside* the container, so no host psql client is required.
db-init:
	docker compose exec -T postgres psql -U sneaker -d sneaker_intel -v ON_ERROR_STOP=1 < db/schema.sql
	docker compose exec -T postgres psql -U sneaker -d sneaker_intel -v ON_ERROR_STOP=1 < db/seeds.sql

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
