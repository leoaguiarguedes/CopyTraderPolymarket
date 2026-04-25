.PHONY: help install dev down logs ps test lint format typecheck migrate migrate-create shell clean

PROJECT := copytrader-polymarket
PY ?= uv run

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies (creates .venv via uv)
	uv sync --extra dev

dev:  ## Start full stack via docker compose (postgres, redis, api, workers)
	docker compose up -d --build
	@echo "API:        http://localhost:8000"
	@echo "Health:     http://localhost:8000/health"
	@echo "Metrics:    http://localhost:8000/metrics"

down:  ## Stop stack
	docker compose down

logs:  ## Tail logs from all services
	docker compose logs -f --tail=100

ps:  ## Show service status
	docker compose ps

test:  ## Run pytest
	$(PY) pytest

test-cov:  ## Run pytest with coverage
	$(PY) pytest --cov=app --cov=workers --cov-report=term-missing

lint:  ## Lint with ruff
	$(PY) ruff check .

format:  ## Format with ruff
	$(PY) ruff format .

typecheck:  ## Type-check with mypy
	$(PY) mypy app workers

migrate:  ## Apply DB migrations
	$(PY) alembic upgrade head

migrate-create:  ## Create new migration: make migrate-create m="description"
	$(PY) alembic revision --autogenerate -m "$(m)"

shell:  ## Open Python shell with app context
	$(PY) python

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
