Stage: 1
Date: 2026-03-09
Branch: chore/restructure-stage-0-setup
Status: Complete

Completed Deliverables:
- Added workspace project registry in `workspace/projects.json` for `api`, `worker`, `web`, `shared`, `storage`, `sources`, `normalizer`, `alerts`, `analytics`, `ai`, and `infra`.
- Added non-breaking workspace task orchestrator in `scripts/restructure/workspace_runner.py` with `list` and `run` actions.
- Added dependency boundary lint script in `scripts/restructure/check_dependency_boundaries.py` to enforce Stage 0 guardrails in code.
- Added Makefile targets `workspace-list`, `workspace-lint`, `workspace-build`, and `boundary-check`.
- Fixed existing API import-order lint issues in `apps/api/routers/grants.py` and `apps/api/routers/llm.py` to keep stage validation green.

Validation Evidence:
- Project registration listed successfully via `uv run python scripts/restructure/workspace_runner.py list`.
- Boundary rules passed via `uv run python scripts/restructure/check_dependency_boundaries.py`.
- API lint/build passed via:
  - `uv run python scripts/restructure/workspace_runner.py run lint --project api`
  - `uv run python scripts/restructure/workspace_runner.py run build --project api`
- Web lint/build passed via:
  - `uv run python scripts/restructure/workspace_runner.py run lint --project web`
  - `uv run python scripts/restructure/workspace_runner.py run build --project web`
- Existing startup flow still works via `./start-all.cmd` with API health `ok` and web readiness `ok`.

Risks / Open Items:
- Boundary enforcement is currently script-based and not yet wired as a mandatory CI gate.
- Worker and infra targets are registered but were not fully executed in this validation set.
- Stage 1 implementation currently resides on `chore/restructure-stage-0-setup`; promote/cherry-pick policy should be decided before Stage 2 branch work.

Decision Log Updates:
- Stage 1 keeps compatibility by layering orchestration scripts over current commands rather than replacing existing startup paths.
- Workspace project metadata is now the source of truth for stage-level project registration and task targeting.

Recommended Next Step:
- Start Stage 2 on `chore/restructure-stage-2-backend-domains` by extracting router/task business logic into explicit service modules and adding contract regression tests for unchanged API response shapes.
