from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from packages.shared.queue import QueueDispatchError, dispatch_or_inline
from packages.sources.discovery import canonicalize_source_url
from packages.sources.registry import get_adapter


@dataclass
class ValidatedDiscoveryCandidate:
    name: str
    url: str
    canonical_url: str
    adapter_type: str
    adapter_name: str
    config: dict[str, Any]
    poll_interval_seconds: int
    tags: list[str]


class SourceServiceError(Exception):
    """Base exception for source-domain service errors."""


class SourceConfigValidationError(SourceServiceError):
    def __init__(self, adapter_name: str, errors: list[str]):
        self.adapter_name = adapter_name
        self.errors = errors
        super().__init__(f"invalid source config for {adapter_name}")


class SourceNotFoundError(SourceServiceError):
    def __init__(self, source_id: str):
        self.source_id = source_id
        super().__init__(f"source not found: {source_id}")


class SourceDispatchFailedError(SourceServiceError):
    def __init__(self, code: str, message: str, error: str, *, task_type: str | None = None):
        self.code = code
        self.message = message
        self.error = error
        self.task_type = task_type
        super().__init__(message)


def validate_source_config(adapter_name: str, config: dict[str, Any] | None) -> list[str]:
    try:
        adapter = get_adapter(adapter_name)
    except KeyError:
        return [f"unknown adapter: {adapter_name}"]
    return adapter.validate_config(config or {})


def ensure_source_config_valid(adapter_name: str, config: dict[str, Any] | None) -> None:
    errors = validate_source_config(adapter_name, config)
    if errors:
        raise SourceConfigValidationError(adapter_name, errors)


def validate_discovery_candidate(
    candidate: dict[str, Any],
    *,
    adapter_names: set[str],
) -> tuple[ValidatedDiscoveryCandidate | None, str | None, list[str]]:
    adapter_name = (candidate.get("adapter_name") or "").strip().lower()
    url = (candidate.get("url") or "").strip()
    canonical_url = canonicalize_source_url(url)
    if adapter_name not in adapter_names or not url or not canonical_url:
        return None, "unknown_adapter_or_missing_url", []

    config = candidate.get("config") or {}
    config_errors = validate_source_config(adapter_name, config)
    if config_errors:
        return None, "invalid_adapter_config", config_errors

    tags = candidate.get("tags") or []
    if not isinstance(tags, list):
        tags = []

    validated = ValidatedDiscoveryCandidate(
        name=candidate.get("name") or f"Discovered {adapter_name}",
        url=url,
        canonical_url=canonical_url,
        adapter_type=candidate.get("adapter_type") or "scraper",
        adapter_name=adapter_name,
        config=config,
        poll_interval_seconds=int(candidate.get("poll_interval_seconds") or 21600),
        tags=tags,
    )
    return validated, None, []


def merge_tags(existing: list[str] | None, additions: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for value in (existing or []) + additions:
        if value and value not in seen:
            seen.add(value)
            merged.append(value)
    return merged


def source_to_dict(source: Any) -> dict[str, Any]:
    return {
        "id": str(source.id),
        "name": source.name,
        "url": source.url,
        "adapter_type": source.adapter_type,
        "adapter_name": source.adapter_name,
        "config": source.config,
        "enabled": source.enabled,
        "poll_interval_seconds": source.poll_interval_seconds,
        "tags": source.tags,
        "last_polled_at": source.last_polled_at.isoformat() if source.last_polled_at else None,
        "last_success_at": source.last_success_at.isoformat() if source.last_success_at else None,
        "last_error": source.last_error,
        "error_count": source.error_count,
        "total_listings": source.total_listings,
        "created_at": source.created_at.isoformat() if source.created_at else None,
        "updated_at": source.updated_at.isoformat() if source.updated_at else None,
    }


def organic_run_to_dict(run: Any) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "status": run.status,
        "triggered_from": run.triggered_from,
        "options": run.options or {},
        "steps": run.steps or [],
        "error": run.error,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def create_source(*, repo: Any, data: Any, adapter_names: set[str]) -> dict[str, Any]:
    if data.adapter_name not in adapter_names:
        raise SourceConfigValidationError(data.adapter_name, [f"unknown adapter: {data.adapter_name}"])

    ensure_source_config_valid(data.adapter_name, data.config)

    existing = repo.get_by_url(data.url)
    if existing:
        raise ValueError("Source with this URL already exists")

    source = repo.create(
        name=data.name,
        url=data.url,
        adapter_type=data.adapter_type,
        adapter_name=data.adapter_name,
        config=data.config or {},
        enabled=data.enabled,
        poll_interval_seconds=data.poll_interval_seconds,
        tags=data.tags or [],
    )
    return source_to_dict(source)


def update_source(*, repo: Any, source_id: str, data: Any) -> dict[str, Any]:
    source = repo.get_by_id(source_id)
    if not source:
        raise SourceNotFoundError(source_id)

    updates = data.model_dump(exclude_unset=True)
    if "config" in updates:
        ensure_source_config_valid(source.adapter_name, updates.get("config") or {})

    updated = repo.update(source_id, **updates)
    return source_to_dict(updated)


def trigger_source_scrape(
    *,
    repo: Any,
    source_id: str,
    force: bool,
    now_iso: Callable[[], str],
    record_event: Callable[..., None],
) -> dict[str, Any]:
    source = repo.get_by_id(source_id)
    if not source:
        raise SourceNotFoundError(source_id)

    from apps.worker.tasks import scrape_source

    timestamp = now_iso()
    try:
        dispatch_result = dispatch_or_inline(
            "scrape",
            "scrape_source",
            {"source_id": source_id, "force": force},
            scrape_source,
        )
    except QueueDispatchError as exc:
        raise SourceDispatchFailedError(
            "scrape_dispatch_failed",
            "Failed to dispatch scrape task to queue.",
            str(exc)[:300],
        ) from exc

    record_event(
        event_type="source_scrape_triggered",
        message="Manual source scrape triggered",
        source_id=source_id,
        context={"force": force, "status": dispatch_result.get("status"), "timestamp": timestamp},
    )
    return {**dispatch_result, "force": force, "timestamp": timestamp}


def trigger_full_organic_search(
    *,
    run_repo: Any,
    force: bool,
    run_alerts: bool,
    run_llm_batch: bool,
    llm_limit: int,
    now_iso: Callable[[], str],
    record_event: Callable[..., None],
) -> dict[str, Any]:
    from apps.worker.tasks import enrich_batch_llm, evaluate_alerts, scrape_all_sources

    steps: list[dict[str, Any]] = []

    def _dispatch_step(queue_name: str, task_type: str, payload: dict[str, Any], inline_fn: Callable[..., Any]) -> dict[str, Any]:
        timestamp = now_iso()
        try:
            dispatch_result = dispatch_or_inline(queue_name, task_type, payload, inline_fn)
        except QueueDispatchError as exc:
            raise SourceDispatchFailedError(
                "pipeline_dispatch_failed",
                f"Failed to dispatch task '{task_type}' to queue.",
                str(exc)[:300],
                task_type=task_type,
            ) from exc
        return {"step": task_type, "timestamp": timestamp, **dispatch_result}

    steps.append(_dispatch_step("scrape", "scrape_all_sources", {"force": force}, scrape_all_sources))
    if run_alerts:
        steps.append(_dispatch_step("alert", "evaluate_alerts", {}, evaluate_alerts))
    if run_llm_batch:
        steps.append(_dispatch_step("llm", "enrich_batch_llm", {"limit": llm_limit}, enrich_batch_llm))

    statuses = {step["status"] for step in steps}
    if statuses == {"dispatched"}:
        status = "dispatched"
    elif statuses == {"processed_inline"}:
        status = "processed_inline"
    else:
        status = "mixed"

    run = run_repo.create(
        status=status,
        triggered_from="api_sources_trigger_all",
        options={
            "force": force,
            "run_alerts": run_alerts,
            "run_llm_batch": run_llm_batch,
            "llm_limit": llm_limit,
        },
        steps=steps,
    )

    record_event(
        event_type="organic_search_triggered",
        message="Full organic search triggered",
        context={
            "status": status,
            "steps": steps,
            "options": {
                "force": force,
                "run_alerts": run_alerts,
                "run_llm_batch": run_llm_batch,
                "llm_limit": llm_limit,
            },
            "timestamp": now_iso(),
        },
    )

    return {
        "run_id": str(run.id),
        "status": status,
        "steps": steps,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def discover_sources_auto(
    *,
    repo: Any,
    auto_enable: bool,
    limit: int,
    adapter_names: set[str],
    candidate_loader: Callable[[], list[dict[str, Any]]],
    now_iso: Callable[[], str],
    record_event: Callable[..., None],
) -> dict[str, Any]:
    created: list[dict[str, Any]] = []
    existing: list[dict[str, Any]] = []
    skipped_invalid: list[dict[str, Any]] = []
    timestamp = now_iso()

    existing_sources = repo.get_all(enabled_only=False)
    existing_by_canonical = {
        canonicalize_source_url(str(source.url or "")): source
        for source in existing_sources
        if canonicalize_source_url(str(source.url or ""))
    }

    for candidate in candidate_loader()[:limit]:
        validated, reason, errors = validate_discovery_candidate(candidate, adapter_names=adapter_names)
        if not validated:
            skipped_invalid.append(
                {
                    "url": candidate.get("url"),
                    "reason": reason,
                    **({"errors": errors} if errors else {}),
                    "timestamp": timestamp,
                }
            )
            continue

        current = existing_by_canonical.get(validated.canonical_url)
        if current:
            existing.append(
                {
                    "id": str(current.id),
                    "url": current.url,
                    "name": current.name,
                    "timestamp": timestamp,
                }
            )
            continue

        tags = merge_tags(
            validated.tags,
            ["auto_discovered"] + ([] if auto_enable else ["pending_approval"]),
        )
        source = repo.create(
            name=validated.name,
            url=validated.url,
            adapter_type=validated.adapter_type,
            adapter_name=validated.adapter_name,
            config=validated.config,
            enabled=auto_enable,
            poll_interval_seconds=validated.poll_interval_seconds,
            tags=tags,
        )
        existing_by_canonical[validated.canonical_url] = source
        created.append(source_to_dict(source))

    record_event(
        event_type="source_discovery_manual_complete",
        message="Manual source discovery completed",
        context={
            "created": len(created),
            "existing": len(existing),
            "skipped_invalid": len(skipped_invalid),
            "auto_enable": auto_enable,
            "limit": limit,
            "timestamp": timestamp,
        },
    )

    return {
        "run_at": timestamp,
        "created": created,
        "existing": existing,
        "skipped_invalid": skipped_invalid,
        "auto_enable": auto_enable,
    }


def list_pending_discovered_sources(*, repo: Any) -> list[dict[str, Any]]:
    pending = [
        source for source in repo.get_all() if isinstance(source.tags, list) and "pending_approval" in source.tags
    ]
    return [source_to_dict(source) for source in pending]


def approve_discovered_source(
    *,
    repo: Any,
    source_id: str,
    now_iso: Callable[[], str],
    record_event: Callable[..., None],
) -> dict[str, Any]:
    source = repo.get_by_id(source_id)
    if not source:
        raise SourceNotFoundError(source_id)

    if not isinstance(source.tags, list):
        source.tags = []

    source.tags = [tag for tag in source.tags if tag != "pending_approval"]
    updated = repo.update(source_id, tags=source.tags, enabled=True)
    record_event(
        event_type="source_discovered_approved",
        message="Discovered source approved",
        source_id=source_id,
        context={"timestamp": now_iso(), "source_name": getattr(updated, "name", None)},
    )
    return source_to_dict(updated)


def trigger_full_discovery(
    *,
    dry_run: bool,
    follow_links: bool,
    limit: int,
    include_grants: bool,
    now_iso: Callable[[], str],
    record_event: Callable[..., None],
) -> dict[str, Any]:
    from apps.worker.tasks import discover_all_sources

    timestamp = now_iso()
    payload = {
        "limit": limit,
        "dry_run": dry_run,
        "follow_links": follow_links,
        "include_grants": include_grants,
    }

    try:
        result = dispatch_or_inline(
            "scrape",
            "discover_all_sources",
            payload,
            lambda **_: discover_all_sources(
                limit=limit,
                dry_run=dry_run,
                follow_links=follow_links,
                include_grants=include_grants,
            ),
        )
    except QueueDispatchError as exc:
        raise SourceDispatchFailedError(
            "discovery_dispatch_failed",
            "Failed to dispatch full discovery task to queue.",
            str(exc)[:300],
            task_type="discover_all_sources",
        ) from exc

    record_event(
        event_type="unified_discovery_triggered",
        message="Unified source + grant discovery triggered via API",
        context={
            **payload,
            "timestamp": timestamp,
            "status": result.get("status"),
        },
    )
    return result


def preview_discovery_candidates(
    *,
    limit: int,
    min_score: float,
    candidate_loader: Callable[..., list[Any]],
) -> dict[str, Any]:
    scored = candidate_loader(use_crawler=True, follow_links=False, reject_below=0.0)
    candidates = [
        {
            "name": sc.candidate.get("name"),
            "url": sc.candidate.get("url"),
            "adapter_name": sc.candidate.get("adapter_name"),
            "adapter_type": sc.candidate.get("adapter_type"),
            "score": sc.score,
            "activation": sc.activation,
            "reasons": sc.reasons,
            "tags": sc.candidate.get("tags", []),
        }
        for sc in scored
        if sc.score >= min_score
    ]
    return {
        "total": len(candidates),
        "shown": min(len(candidates), limit),
        "candidates": candidates[:limit],
    }