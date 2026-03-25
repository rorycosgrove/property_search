# Release Notes - March 2026

## Summary
This release stabilizes the LLM analysis flow and modernizes the map workspace UI for faster property research.

## LLM Reliability
- Fixed provider resolution bug in `packages/ai/service.py`.
- Added `llm_enabled` gating for enrichment entry points:
  - `apps/api/routers/llm.py`
  - `apps/worker/tasks.py`
- Added explicit API behavior for disabled/misconfigured LLM dispatch:
  - `503` when LLM is disabled
  - inline fallback when queue URL is unconfigured
  - `503` on unexpected queue runtime dispatch failures
- Hardened Bedrock provider with categorized invocation errors and invalid JSON handling in `packages/ai/bedrock_provider.py`.
- Improved LLM observability by including `enabled` status and disabled reason in `/api/v1/llm/health`.

## Frontend UX and Map Improvements
- Added modern responsive top navigation with active route states and mobile menu:
  - `web/src/components/TopNav.tsx`
  - integrated in `web/src/app/layout.tsx`
- Refactored workspace to map-first responsive layout with panel toggles:
  - `web/src/app/page.tsx`
  - `web/src/lib/stores.ts`
- Added marker hover cards and click-to-focus map behavior:
  - `web/src/components/PropertyMap.tsx`
  - `web/src/app/globals.css`
- Updated filter surface for compact responsive controls:
  - `web/src/components/FilterBar.tsx`

## Testing and Validation
- Added API tests for enrichment dispatch guards in `tests/test_api.py`.
- Added provider tests for Bedrock error paths in `tests/test_bedrock_provider.py`.
- Validation run results:
  - `pytest .\\tests\\test_api.py -k "llm or enrich"` passed
  - `pytest .\\tests\\test_bedrock_provider.py` passed
  - `npm exec tsc -- --noEmit` passed

## Launch Notes
- Local app launch verified:
  - API: `http://localhost:8000/health`
  - Frontend: `http://localhost:3000`
- LLM health endpoint now explicitly reports disabled state when not enabled/configured.

## Local Runtime Resilience
- Added `scripts/dev/cleanup-local.ps1` to clear stale API/frontend listeners and orphaned dev processes.
- Added `stop-local.cmd` as a one-command local cleanup entry point.
- Updated `start-api-llm.cmd` and `web/start-dev.cmd` to run targeted cleanup before startup.

## Reliability Hardening Milestone (Mar 9, 2026)

### What Landed
- Queue dispatch contract unified across source and LLM trigger paths via `dispatch_or_inline` and typed `QueueDispatchError` handling.
- API error classification hardened so inline task failures are no longer mislabeled as queue dispatch failures.
- Worker orchestration ownership clarified: canonical implementations remain in `apps/worker/tasks.py`; `packages/worker/service.py` is explicit compatibility shim.
- Backend log operational APIs expanded:
  - `GET /api/v1/admin/backend-logs`
  - `GET /api/v1/admin/backend-logs/summary`
  - Existing `logs/*` admin diagnostics retained and validated.
- Health response expanded with backend signal: `backend_errors_last_hour`.
- Migration safety covered for `alembic/versions/007_backend_logs.py` with dedicated metadata/upgrade/downgrade tests.
- Repository-level coverage added for backend log querying and summaries.
- Worker observability extended with explicit backend log events for alert and LLM task outcomes.
- Focused reliability coverage command added: `make test-cov-plan`.

### Validation Snapshot
- Full suite reached green after hardening iterations: `151 passed`.
- Focused reliability workflow validated:
  - `make test-cov-plan`
- Key regression areas explicitly tested:
  - queue dispatch failure mapping
  - inline failure propagation
  - backend log filtering/summary paths
  - worker task observability event branches

## Data-First Search Completion (Mar 25, 2026)

### What Landed
- Persisted address matching primitives (`address_normalized`, `fuzzy_address_hash`) for both active and sold properties.
- Trigram infrastructure enabled (`pg_trgm` + GIN trigram indexes) with migration coverage and shortened safe revision IDs.
- Confidence-gated sold comparable-sales endpoint added:
  - `GET /api/v1/properties/{id}/sold-comps`
- Property keyword search upgraded from pure substring matching to trigram-assisted matching with relevance sorting (`sort_by=relevance`).
- Geocoder upgraded with persistent DB-backed cache support.
- Search benchmarking tooling added with enforceable gates and curated query set:
  - `scripts/benchmark_search_quality.py`
  - `scripts/search_benchmark_queries.txt`
  - `make benchmark-search`
  - `make benchmark-search-gate`

### Calibration Snapshot
- Curated benchmark gate run passes with current defaults:
  - `result_coverage`: 0.9375
  - `avg_top_overlap`: 0.5333
  - `avg_top3_overlap`: 0.5333
- Gate thresholds are centralized in `packages/shared/constants.py`:
  - `SEARCH_BENCHMARK_MIN_RESULT_COVERAGE`
  - `SEARCH_BENCHMARK_MIN_TOP_OVERLAP`
  - `SEARCH_BENCHMARK_MIN_TOP3_OVERLAP`

### Commit Readiness Checklist
- Apply migrations: `python -m alembic upgrade head`
- Refresh persisted matching fields: `python scripts/backfill_address_match_fields.py`
- Validate focused search stack:
  - `python -m pytest -q tests/test_property_repository.py tests/test_sold_repository.py tests/test_api.py tests/test_property_service.py tests/test_search_quality_benchmark.py`
- Validate search quality gates:
  - `make benchmark-search-gate`
