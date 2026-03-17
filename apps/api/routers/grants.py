"""Grant and incentive endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from packages.grants.engine import evaluate_property_grants
from packages.grants.service import (
    GrantNotFoundError,
    activate_discovered_grant as grants_activate_discovered,
    create_grant as grants_create,
    discover_grant_programs as grants_discover,
    get_grant as grants_get,
    get_property_grants as grants_property,
    grant_to_dict,
    list_discovered_grants as grants_list_discovered,
    list_grants as grants_list,
    update_grant as grants_update,
)
from packages.shared.schemas import GrantProgramCreate, GrantProgramUpdate
from packages.storage.database import get_db_session
from packages.storage.repositories import PropertyRepository

router = APIRouter()


@router.get("")
def list_grants(
    country: str | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db_session),
):
    return grants_list(db, country=country, active_only=active_only)


@router.post("", status_code=201)
def create_grant(data: GrantProgramCreate, db: Session = Depends(get_db_session)):
    return grants_create(db, data)


@router.get("/{grant_id}")
def get_grant(grant_id: str, db: Session = Depends(get_db_session)):
    return grants_get(db, grant_id)


@router.patch("/{grant_id}")
def update_grant(grant_id: str, data: GrantProgramUpdate, db: Session = Depends(get_db_session)):
    return grants_update(db, grant_id, data)


@router.get("/property/{property_id}")
def get_property_grants(property_id: str, db: Session = Depends(get_db_session)):
    return grants_property(db, property_id)


@router.post("/property/{property_id}/evaluate")
def evaluate_property_grants_endpoint(property_id: str, db: Session = Depends(get_db_session)):
    property_repo = PropertyRepository(db)
    prop = property_repo.get_by_id(property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    matches = evaluate_property_grants(db, property_obj=prop)
    return {"property_id": property_id, "matches": len(matches), "status": "evaluated"}


@router.post("/discover")
def discover_grant_programs_endpoint(
    dry_run: bool = Query(False, description="Preview without writing to the database"),
):
    """Discover new grant programs from Irish/NI government portals."""
    return grants_discover(dry_run=dry_run)


@router.get("/discovered/pending")
def list_discovered_grants(db: Session = Depends(get_db_session)):
    """List grants discovered by the crawler and pending review."""
    return grants_list_discovered(db)


@router.post("/{grant_id}/activate")
def activate_discovered_grant(grant_id: str, db: Session = Depends(get_db_session)):
    """Activate a discovered grant after human review."""
    try:
        return grants_activate_discovered(db, grant_id)
    except GrantNotFoundError as exc:
        raise HTTPException(404, "Grant not found") from exc


def _grant_to_dict(grant) -> dict:
    return grant_to_dict(grant)
