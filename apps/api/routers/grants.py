"""Grant and incentive endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from packages.grants.engine import evaluate_property_grants
from packages.grants.service import (
    create_grant as grants_create,
    get_grant as grants_get,
    get_property_grants as grants_property,
    list_grants as grants_list,
    update_grant as grants_update,
)
from packages.shared.schemas import GrantProgramCreate, GrantProgramUpdate
from packages.storage.database import get_db_session
from packages.storage.repositories import GrantProgramRepository, PropertyGrantMatchRepository, PropertyRepository

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
    db: Session = Depends(get_db_session),
):
    """Discover new grant programs from Irish/NI government portals."""
    from packages.grants.discovery import discover_grant_programs
    return discover_grant_programs(dry_run=dry_run)


@router.get("/discovered/pending")
def list_discovered_grants(db: Session = Depends(get_db_session)):
    """List grants discovered by the crawler and pending review."""
    repo = GrantProgramRepository(db)
    all_grants = repo.list_programs(active_only=False)
    pending = [g for g in all_grants if "DISCOVERED" in (g.code or "")]
    return [_grant_to_dict(g) for g in pending]


@router.post("/{grant_id}/activate")
def activate_discovered_grant(grant_id: str, db: Session = Depends(get_db_session)):
    """Activate a discovered grant after human review."""
    repo = GrantProgramRepository(db)
    grant = repo.get_by_id(grant_id)
    if not grant:
        raise HTTPException(404, "Grant not found")
    updated = repo.update(grant_id, active=True)
    db.commit()
    return _grant_to_dict(updated)


def _grant_to_dict(grant) -> dict:
    return {
        "id": str(grant.id),
        "code": grant.code,
        "name": grant.name,
        "country": grant.country,
        "region": grant.region,
        "authority": grant.authority,
        "description": grant.description,
        "eligibility_rules": grant.eligibility_rules or {},
        "benefit_type": grant.benefit_type,
        "max_amount": float(grant.max_amount) if grant.max_amount is not None else None,
        "currency": grant.currency,
        "active": grant.active,
        "valid_from": grant.valid_from.isoformat() if grant.valid_from else None,
        "valid_to": grant.valid_to.isoformat() if grant.valid_to else None,
        "source_url": grant.source_url,
        "created_at": grant.created_at.isoformat() if grant.created_at else None,
        "updated_at": grant.updated_at.isoformat() if grant.updated_at else None,
    }
