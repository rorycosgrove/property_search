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
  - `503` when `LLM_QUEUE_URL` is missing
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
