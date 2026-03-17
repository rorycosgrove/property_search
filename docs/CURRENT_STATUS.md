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
