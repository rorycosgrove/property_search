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

1. Add lifecycle action history endpoint and UI timeline for previous runs.
2. Add scheduled execution metadata (cadence + policy visibility) in admin surfaces.
3. Keep destructive execution disabled until explicit feature flag and rollback strategy are implemented.
