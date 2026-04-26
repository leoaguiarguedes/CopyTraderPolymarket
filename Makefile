.PHONY: help install dev down logs ps test lint format typecheck migrate migrate-create shell clean web-dev web-build web-install

PROJECT := copytrader-polymarket
PY ?= uv run

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install Python dependencies (creates .venv via uv)
	uv sync --extra dev

dev:  ## Start full stack (postgres, redis, api, workers, web)
	docker compose up -d --build
	@echo ""
	@echo "  Dashboard:  http://localhost:3000"
	@echo "  API:        http://localhost:8000"
	@echo "  API Docs:   http://localhost:8000/docs"
	@echo "  Metrics:    http://localhost:8000/metrics"

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

migrate:  ## Apply DB migrations (inside container)
	docker compose exec api alembic upgrade head

migrate-local:  ## Apply DB migrations (local venv)
	$(PY) alembic upgrade head

migrate-create:  ## Create new migration: make migrate-create m="description"
	$(PY) alembic revision --autogenerate -m "$(m)"

discover:  ## Discover and score wallets, output to config/tracked_wallets.yaml
	$(PY) python scripts/discover_wallets.py --days 90 --limit 500

shell:  ## Open Python shell with app context
	$(PY) python

web-install:  ## Install web frontend dependencies
	cd web && npm install

web-dev:  ## Start Next.js dev server (hot reload) — requires NEXT_PUBLIC_API_URL
	cd web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

web-build:  ## Build Next.js for production
	cd web && npm run build

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
