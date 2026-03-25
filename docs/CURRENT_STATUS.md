# Current Status

This document replaces older point-in-time analysis docs that are no longer reliable (`CODE_ISSUES_ANALYSIS.md`, `BEST_PRACTICES_IMPLEMENTATION.md`).

## Repository State Guidance

Use these sources of truth for current behavior:

- Runtime status and queue depth: `status-local.cmd`
- Local startup orchestration: `start-all.cmd`, `start-local-services.cmd`, `start-sqs-worker.cmd`
- Operational updates: `docs/RELEASE_NOTES_MAR_2026.md`
- Architecture and module boundaries: `docs/ARCHITECTURE.md`
- Local setup and troubleshooting: `docs/QUICKSTART.md`, `docs/DEVELOPMENT.md`, `WINDOWS_SETUP.md`

## Active Local Runtime Expectations

- Queue mode is opt-in for local runs (`LOCAL_USE_SQS=1`).
- Local queue dispatch requires `SCRAPE_QUEUE_URL`, `LLM_QUEUE_URL`, and `ALERT_QUEUE_URL`.
- Reference corpus refresh can be enabled with `REFERENCE_DOCUMENT_REFRESH_ON_SCRAPE=1`.
- Schema and extension prerequisites for local worker stability:
  - Run migrations: `python -m alembic upgrade head`
  - Ensure PostGIS is enabled in the local database.

## Documentation Policy

To keep docs accurate:

- Prefer capability-based descriptions over brittle hardcoded counts/versions.
- Keep dated milestone details in release notes, not in evergreen setup docs.
- If behavior changes in worker orchestration, update `QUICKSTART.md`, `DEVELOPMENT.md`, and `WINDOWS_SETUP.md` together.

## Plan Update (Mar 22, 2026)

Functional-error remediation was applied to Phase 4 operability work:

- Added lifecycle action execution endpoint with strict safety guard (dry-run only):
  - `POST /api/v1/admin/data-lifecycle/actions/{action}`
  - Supported actions: `archive_properties`, `archive_backend_logs`, `rollup_price_and_timeline`
- Added backend audit logging for lifecycle dry-runs (`admin_data_lifecycle_action`) to improve operator traceability.
- Added admin UI controls for lifecycle dry-runs and result feedback.
- Added API and service regression coverage for lifecycle report/action flows.

Validation snapshot:

- Admin lifecycle focused tests pass:
  - `tests/test_admin_service.py`
  - `tests/test_admin_lifecycle_api.py`

Remaining Phase 4 implementation track:

1. Keep destructive execution disabled until explicit feature flag and rollback strategy are implemented.

Progress update:

- Completed lifecycle action history visibility:
  - `GET /api/v1/admin/data-lifecycle/history`
  - Admin UI now shows recent lifecycle run timeline from backend logs.
- Added lifecycle history API regression test coverage (`tests/test_admin_lifecycle_api.py`).
- Completed scheduled execution metadata visibility:
  - `GET /api/v1/admin/data-lifecycle/schedule`
  - Admin UI now shows cadence and policy metadata (scrape/RSS/PPR intervals, log retention, execution mode).
- Added lifecycle execution safety contract (feature-flag + rollback prerequisites):
  - Config settings: `lifecycle_destructive_execution_enabled`, `lifecycle_rollback_plan_id`.
  - Lifecycle action execution now enforces both controls before any non-dry-run request is considered.
  - Schedule metadata now exposes `destructive_enabled`, `rollback_plan_id_configured`, and `destructive_ready` for operator readiness checks.
  - Regression coverage added in admin service + API lifecycle tests for the new guardrails.

## Data-First Search Status (Mar 25, 2026)

The data-quality execution track is complete through search calibration gates.

Completed milestones:
- Ingestion correctness and deterministic PPR import accounting.
- Persisted matching fields and backfill support.
- Trigram infrastructure and relevance sorting in property search.
- Confidence-gated sold comparable-sales endpoint.
- Persistent geocode cache path.
- Curated search benchmark and enforceable quality gates.

Operational benchmark command:
- `make benchmark-search-gate`

This command runs the curated query set in `scripts/search_benchmark_queries.txt`
and exits non-zero when gate thresholds are missed.
