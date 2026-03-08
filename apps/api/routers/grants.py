"""Grant and incentive endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from packages.shared.schemas import GrantProgramCreate, GrantProgramUpdate
from packages.storage.database import get_db_session
from packages.storage.repositories import GrantProgramRepository, PropertyGrantMatchRepository

router = APIRouter()


@router.get("")
def list_grants(
    country: str | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db_session),
):
    repo = GrantProgramRepository(db)
    grants = repo.list_programs(country=country, active_only=active_only)
    return [_grant_to_dict(g) for g in grants]


@router.post("", status_code=201)
def create_grant(data: GrantProgramCreate, db: Session = Depends(get_db_session)):
    repo = GrantProgramRepository(db)
    existing = repo.get_by_code(data.code)
    if existing:
        raise HTTPException(409, "Grant with this code already exists")

    grant = repo.create(**data.model_dump())
    return _grant_to_dict(grant)


@router.get("/{grant_id}")
def get_grant(grant_id: str, db: Session = Depends(get_db_session)):
    repo = GrantProgramRepository(db)
    grant = repo.get_by_id(grant_id)
    if not grant:
        raise HTTPException(404, "Grant not found")
    return _grant_to_dict(grant)


@router.patch("/{grant_id}")
def update_grant(grant_id: str, data: GrantProgramUpdate, db: Session = Depends(get_db_session)):
    repo = GrantProgramRepository(db)
    if not repo.get_by_id(grant_id):
        raise HTTPException(404, "Grant not found")

    updated = repo.update(grant_id, **data.model_dump(exclude_unset=True))
    return _grant_to_dict(updated)


@router.get("/property/{property_id}")
def get_property_grants(property_id: str, db: Session = Depends(get_db_session)):
    repo = PropertyGrantMatchRepository(db)
    matches = repo.list_for_property(property_id)

    result = []
    for m in matches:
        result.append(
            {
                "id": str(m.id),
                "property_id": str(m.property_id),
                "grant_program_id": str(m.grant_program_id),
                "status": m.status,
                "reason": m.reason,
                "estimated_benefit": float(m.estimated_benefit) if m.estimated_benefit is not None else None,
                "metadata": m.metadata_json or {},
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "grant_program": _grant_to_dict(m.grant_program) if m.grant_program else None,
            }
        )

    return result


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
