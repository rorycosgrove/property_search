"""Saved search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from packages.saved_searches.service import (
    SavedSearchNotFoundError,
    create_saved_search_payload,
    delete_saved_search_payload,
    get_saved_search_payload,
    list_saved_searches_payload,
    update_saved_search_payload,
)
from packages.shared.schemas import SavedSearchCreate, SavedSearchUpdate
from packages.storage.database import get_db_session
from packages.storage.repositories import SavedSearchRepository

router = APIRouter()


@router.get("")
def list_saved_searches(db: Session = Depends(get_db_session)):
    """List all saved searches."""
    repo = SavedSearchRepository(db)
    return list_saved_searches_payload(repo=repo)


@router.post("", status_code=201)
def create_saved_search(data: SavedSearchCreate, db: Session = Depends(get_db_session)):
    """Create a new saved search."""
    repo = SavedSearchRepository(db)
    return create_saved_search_payload(repo=repo, data=data)


@router.get("/{search_id}")
def get_saved_search(search_id: str, db: Session = Depends(get_db_session)):
    """Get a saved search by ID."""
    repo = SavedSearchRepository(db)
    try:
        return get_saved_search_payload(repo=repo, search_id=search_id)
    except SavedSearchNotFoundError as exc:
        raise HTTPException(404, "Saved search not found") from exc


@router.patch("/{search_id}")
def update_saved_search(
    search_id: str,
    data: SavedSearchUpdate,
    db: Session = Depends(get_db_session),
):
    """Update a saved search."""
    repo = SavedSearchRepository(db)
    try:
        return update_saved_search_payload(repo=repo, search_id=search_id, data=data)
    except SavedSearchNotFoundError as exc:
        raise HTTPException(404, "Saved search not found") from exc


@router.delete("/{search_id}", status_code=204)
def delete_saved_search(search_id: str, db: Session = Depends(get_db_session)):
    """Delete a saved search."""
    repo = SavedSearchRepository(db)
    try:
        delete_saved_search_payload(repo=repo, search_id=search_id)
    except SavedSearchNotFoundError as exc:
        raise HTTPException(404, "Saved search not found") from exc
