"""Saved search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from packages.shared.schemas import SavedSearchCreate, SavedSearchUpdate
from packages.storage.database import get_db_session
from packages.storage.repositories import SavedSearchRepository

router = APIRouter()


@router.get("")
def list_saved_searches(db: Session = Depends(get_db_session)):
    """List all saved searches."""
    repo = SavedSearchRepository(db)
    searches = repo.get_all()
    return [_to_dict(s) for s in searches]


@router.post("", status_code=201)
def create_saved_search(data: SavedSearchCreate, db: Session = Depends(get_db_session)):
    """Create a new saved search."""
    repo = SavedSearchRepository(db)
    search = repo.create(
        name=data.name,
        criteria=data.criteria.model_dump() if data.criteria else {},
        notify_new_listings=data.notify_new_listings,
        notify_price_drops=data.notify_price_drops,
        notify_method=data.notify_method,
        email=data.email,
        is_active=True,
    )
    return _to_dict(search)


@router.get("/{search_id}")
def get_saved_search(search_id: str, db: Session = Depends(get_db_session)):
    """Get a saved search by ID."""
    repo = SavedSearchRepository(db)
    search = repo.get_by_id(search_id)
    if not search:
        raise HTTPException(404, "Saved search not found")
    return _to_dict(search)


@router.patch("/{search_id}")
def update_saved_search(
    search_id: str,
    data: SavedSearchUpdate,
    db: Session = Depends(get_db_session),
):
    """Update a saved search."""
    repo = SavedSearchRepository(db)
    if not repo.get_by_id(search_id):
        raise HTTPException(404, "Saved search not found")

    updates = data.model_dump(exclude_unset=True)
    if "criteria" in updates and updates["criteria"]:
        updates["criteria"] = updates["criteria"].model_dump() if hasattr(updates["criteria"], "model_dump") else updates["criteria"]

    updated = repo.update(search_id, **updates)
    return _to_dict(updated)


@router.delete("/{search_id}", status_code=204)
def delete_saved_search(search_id: str, db: Session = Depends(get_db_session)):
    """Delete a saved search."""
    repo = SavedSearchRepository(db)
    if not repo.get_by_id(search_id):
        raise HTTPException(404, "Saved search not found")
    repo.delete(search_id)


def _to_dict(search) -> dict:
    return {
        "id": str(search.id),
        "name": search.name,
        "criteria": search.criteria,
        "notify_new_listings": search.notify_new_listings,
        "notify_price_drops": search.notify_price_drops,
        "notify_method": search.notify_method,
        "email": search.email,
        "is_active": search.is_active,
        "last_matched_at": search.last_matched_at.isoformat() if search.last_matched_at else None,
        "created_at": search.created_at.isoformat() if search.created_at else None,
        "updated_at": search.updated_at.isoformat() if search.updated_at else None,
    }
