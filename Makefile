.PHONY: up down logs seed scrape test test-cov lint format migrate deploy synth diff destroy help

# ── Local PostgreSQL (dev) ────────────────────
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# ── Data ──────────────────────────────────────
seed:
	uv run python scripts/seed.py

scrape:
	uv run python -c "from apps.worker.tasks import scrape_all_sources; scrape_all_sources()"

import-ppr:
	uv run python scripts/import_ppr.py

# ── Development ───────────────────────────────
test:
	uv run pytest -v

test-cov:
	uv run pytest --cov=packages --cov-report=html --cov-report=term-missing

test-cov-plan:
	uv run pytest tests/test_api.py tests/test_worker_tasks.py tests/test_worker_service.py tests/test_queue.py tests/test_backend_log_repository.py tests/test_migration_backend_logs.py --cov=apps.api.routers.sources --cov=apps.api.routers.llm --cov=apps.api.routers.admin --cov=apps.api.routers.health --cov=apps.worker.tasks --cov=packages.shared.queue --cov=packages.storage.repositories --cov-report=term-missing

lint:
	uv run ruff check packages/ apps/ tests/
	uv run mypy packages/ apps/

format:
	uv run black packages/ apps/ tests/
	uv run ruff check --fix packages/ apps/ tests/

# ── Database ──────────────────────────────────
migrate:
	uv run alembic upgrade head

migration:
	uv run alembic revision --autogenerate -m "$(msg)"

db-shell:
	docker compose exec postgres psql -U propertysearch -d propertysearch

# ── AWS CDK ───────────────────────────────────
synth:
	cd infra && npx cdk synth

diff:
	cd infra && npx cdk diff

deploy:
	cd infra && npx cdk deploy --all --require-approval broadening

destroy:
	cd infra && npx cdk destroy --all

# ── Cleanup ───────────────────────────────────
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf infra/cdk.out

help:
	@echo "Irish Property Search Dashboard (AWS Serverless)"
	@echo "================================================="
	@echo ""
	@echo "Local Development:"
	@echo "  make up          - Start local PostgreSQL"
	@echo "  make down        - Stop local PostgreSQL"
	@echo "  make logs        - Follow PostgreSQL logs"
	@echo "  make seed        - Seed initial data sources"
	@echo "  make scrape      - Trigger manual scrape"
	@echo "  make import-ppr  - Import Property Price Register data"
	@echo ""
	@echo "Development:"
	@echo "  make test        - Run tests"
	@echo "  make test-cov    - Run tests with coverage"
	@echo "  make test-cov-plan - Run focused reliability-plan coverage checks"
	@echo "  make lint        - Run linters"
	@echo "  make format      - Auto-format code"
	@echo "  make migrate     - Run database migrations"
	@echo "  make db-shell    - Open database shell"
	@echo ""
	@echo "AWS CDK:"
	@echo "  make synth       - Synthesize CloudFormation templates"
	@echo "  make diff        - Preview infrastructure changes"
	@echo "  make deploy      - Deploy all stacks to AWS"
	@echo "  make destroy     - Tear down all stacks"
	@echo ""
	@echo "  make clean       - Remove all local data and caches"
