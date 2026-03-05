.PHONY: up down build rebuild logs seed scrape test lint format migrate help

# ── Docker Compose ────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

rebuild:
	docker compose down
	docker compose build --no-cache
	docker compose up -d

logs:
	docker compose logs -f

logs-worker:
	docker compose logs -f worker llm-worker

logs-api:
	docker compose logs -f api

# ── Data ──────────────────────────────────────
seed:
	docker compose exec api python scripts/seed.py

scrape:
	docker compose exec api python -c "from apps.worker.tasks import scrape_all_sources_task; scrape_all_sources_task.delay()"

import-ppr:
	docker compose exec api python scripts/import_ppr.py

# ── Development ───────────────────────────────
test:
	uv run pytest -v

test-cov:
	uv run pytest --cov=packages --cov-report=html --cov-report=term-missing

lint:
	uv run ruff check packages/ apps/ tests/
	uv run mypy packages/ apps/

format:
	uv run black packages/ apps/ tests/
	uv run ruff check --fix packages/ apps/ tests/

# ── Database ──────────────────────────────────
migrate:
	docker compose exec api alembic upgrade head

migration:
	docker compose exec api alembic revision --autogenerate -m "$(msg)"

db-shell:
	docker compose exec postgres psql -U propertysearch -d propertysearch

# ── Cleanup ───────────────────────────────────
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

help:
	@echo "Irish Property Search Dashboard"
	@echo "================================"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make build       - Build Docker images"
	@echo "  make rebuild     - Full rebuild (no cache)"
	@echo "  make logs        - Follow all service logs"
	@echo "  make seed        - Seed initial data sources"
	@echo "  make scrape      - Trigger manual scrape"
	@echo "  make import-ppr  - Import Property Price Register data"
	@echo "  make test        - Run tests"
	@echo "  make test-cov    - Run tests with coverage"
	@echo "  make lint        - Run linters"
	@echo "  make format      - Auto-format code"
	@echo "  make migrate     - Run database migrations"
	@echo "  make db-shell    - Open database shell"
	@echo "  make clean       - Remove all data and caches"
