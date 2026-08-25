.DEFAULT_GOAL := help
.PHONY: help install db migrate api ml web dev ingest smoke test lint

API := apps/api
ML  := apps/ml
WEB := apps/web

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies for every app
	cd $(API) && uv sync
	cd $(ML) && uv sync
	cd $(WEB) && pnpm install

db:  ## Start the local PostgreSQL container
	cd $(API) && docker compose up -d db

migrate:  ## Apply backend migrations
	cd $(API) && uv run alembic upgrade head

api:  ## Run the FastAPI backend (http://localhost:8000)
	cd $(API) && uv run python -m boxbox_api.main

web:  ## Run the Vite frontend (http://localhost:5173)
	cd $(WEB) && pnpm dev

ml:  ## Open JupyterLab against the ML workspace
	cd $(ML) && uv run --extra notebooks jupyter lab

ingest:  ## Pull race laps into apps/ml/data/laps.parquet (SEASONS="2023 2024")
	cd $(ML) && uv run boxbox-ingest --seasons $(or $(SEASONS),2022 2023 2024)

smoke:  ## Verify the ingest -> features pipeline on two known races
	cd $(ML) && uv run python scripts/smoke.py

dev:  ## Reminder: api and web need separate terminals
	@echo "Run 'make api' and 'make web' in separate terminals."

test:  ## Run every test suite
	cd $(API) && uv run pytest
	cd $(ML) && uv run pytest
	cd $(WEB) && pnpm test

lint:  ## Lint every app
	cd $(API) && uv run ruff check .
	cd $(ML) && uv run ruff check .
	cd $(WEB) && pnpm lint
