"""Source management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from packages.shared.schemas import SourceCreate, SourceUpdate
from packages.sources.registry import get_adapter_names, list_adapters
from packages.storage.database import get_db_session
from packages.storage.repositories import SourceRepository

router = APIRouter()


@router.get("")
def list_sources(db: Session = Depends(get_db_session)):
    """List all configured sources."""
    repo = SourceRepository(db)
    sources = repo.get_all()
    return [_to_dict(s) for s in sources]


@router.post("", status_code=201)
def create_source(data: SourceCreate, db: Session = Depends(get_db_session)):
    """Create a new source configuration."""
    repo = SourceRepository(db)

    # Validate adapter name
    if data.adapter_name not in get_adapter_names():
        raise HTTPException(400, f"Unknown adapter: {data.adapter_name}")

    existing = repo.get_by_url(data.url)
    if existing:
        raise HTTPException(409, "Source with this URL already exists")

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
    return _to_dict(source)


@router.get("/adapters")
def list_available_adapters():
    """List all available source adapters with their config schemas."""
    return [a.model_dump() for a in list_adapters()]


@router.get("/{source_id}")
def get_source(source_id: str, db: Session = Depends(get_db_session)):
    """Get a single source by ID."""
    repo = SourceRepository(db)
    source = repo.get_by_id(source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    return _to_dict(source)


@router.patch("/{source_id}")
def update_source(source_id: str, data: SourceUpdate, db: Session = Depends(get_db_session)):
    """Update a source configuration."""
    repo = SourceRepository(db)
    source = repo.get_by_id(source_id)
    if not source:
        raise HTTPException(404, "Source not found")

    updates = data.model_dump(exclude_unset=True)
    updated = repo.update(source_id, **updates)
    return _to_dict(updated)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: str, db: Session = Depends(get_db_session)):
    """Delete a source."""
    repo = SourceRepository(db)
    if not repo.get_by_id(source_id):
        raise HTTPException(404, "Source not found")
    repo.delete(source_id)


@router.post("/{source_id}/trigger")
def trigger_scrape(source_id: str, db: Session = Depends(get_db_session)):
    """Manually trigger a scrape for a source."""
    repo = SourceRepository(db)
    source = repo.get_by_id(source_id)
    if not source:
        raise HTTPException(404, "Source not found")

    from packages.shared.queue import send_task
    message_id = send_task("scrape", "scrape_source", {"source_id": source_id})
    return {"task_id": message_id, "status": "dispatched"}


def _to_dict(source) -> dict:
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
