from __future__ import annotations

from sqlalchemy.orm import Session
from fastapi import HTTPException

from packages.storage.repositories import GrantProgramRepository, PropertyGrantMatchRepository, PropertyRepository
from packages.grants.engine import evaluate_property_grants
from packages.shared.schemas import GrantProgramCreate, GrantProgramUpdate


class GrantNotFoundError(Exception):
    def __init__(self, grant_id: str):
        self.grant_id = grant_id
        super().__init__(f"grant not found: {grant_id}")


def list_grants(db: Session, country: str | None = None, active_only: bool = True):
    repo = GrantProgramRepository(db)
    grants = repo.list_programs(country=country, active_only=active_only)
    return [grant_to_dict(g) for g in grants]


def create_grant(db: Session, data: GrantProgramCreate):
    repo = GrantProgramRepository(db)
    existing = repo.get_by_code(data.code)
    if existing:
        raise HTTPException(409, "Grant with this code already exists")
    grant = repo.create(**data.model_dump())
    return grant_to_dict(grant)


def get_grant(db: Session, grant_id: str):
    repo = GrantProgramRepository(db)
    grant = repo.get_by_id(grant_id)
    if not grant:
        raise HTTPException(404, "Grant not found")
    return grant_to_dict(grant)


def update_grant(db: Session, grant_id: str, data: GrantProgramUpdate):
    repo = GrantProgramRepository(db)
    if not repo.get_by_id(grant_id):
        raise HTTPException(404, "Grant not found")
    updated = repo.update(grant_id, **data.model_dump(exclude_unset=True))
    return grant_to_dict(updated)


def get_property_grants(db: Session, property_id: str):
    property_repo = PropertyRepository(db)
    if not property_repo.get_by_id(property_id):
        raise HTTPException(404, "Property not found")
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
                "grant_program": grant_to_dict(m.grant_program) if m.grant_program else None,
            }
        )
    return result


def discover_grant_programs(*, dry_run: bool = False) -> dict:
    from packages.grants.discovery import discover_grant_programs as discover

    return discover(dry_run=dry_run)


def list_discovered_grants(db: Session) -> list[dict]:
    repo = GrantProgramRepository(db)
    all_grants = repo.list_programs(active_only=False)
    pending = [grant for grant in all_grants if "DISCOVERED" in (grant.code or "")]
    return [grant_to_dict(grant) for grant in pending]


def activate_discovered_grant(db: Session, grant_id: str) -> dict:
    repo = GrantProgramRepository(db)
    grant = repo.get_by_id(grant_id)
    if not grant:
        raise GrantNotFoundError(grant_id)
    updated = repo.update(grant_id, active=True)
    db.commit()
    return grant_to_dict(updated)


def grant_to_dict(grant) -> dict:
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
