"""Property CRUD and search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from packages.properties.service import (
    PropertyNotFoundError,
    PropertyValidationError,
    get_intelligence_payload,
    get_price_history_payload,
    get_property_payload,
    get_similar_payload,
    get_timeline_payload,
    list_properties_payload,
)
from packages.properties.service import get_brief_payload
from packages.shared.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from packages.shared.schemas import PropertyListResponse, PropertyResponse, PropertyTimelineEventResponse
from packages.storage.database import get_db_session
from packages.storage.repositories import (
    PriceHistoryRepository,
    PropertyDocumentRepository,
    PropertyRepository,
    PropertyTimelineRepository,
)

router = APIRouter()


@router.get("", response_model=PropertyListResponse)
def list_properties(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    county: str | None = Query(None, max_length=100),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_beds: int | None = Query(None, ge=0, le=20),
    max_beds: int | None = Query(None, ge=0, le=20),
    property_types: str | None = Query(None, description="Comma-separated types"),
    sale_type: str | None = None,
    keywords: str | None = Query(None, max_length=500),
    ber_ratings: str | None = Query(None, description="Comma-separated BER ratings"),
    eligible_only: bool = Query(False, description="Only include properties with confirmed eligible grants"),
    min_eligible_grants_total: float | None = Query(None, ge=0, description="Minimum confirmed eligible grant total"),
    sort_by: str = Query("created_at", pattern="^(price|net_price|created_at|date|beds|bedrooms)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    radius_km: float | None = Query(None, ge=0.1, le=100),
    db: Session = Depends(get_db_session),
):
    """List/search properties with full filtering, sorting, and pagination."""
    repo = PropertyRepository(db)
    try:
        return list_properties_payload(
            repo=repo,
            page=page,
            size=size,
            county=county,
            min_price=min_price,
            max_price=max_price,
            min_beds=min_beds,
            max_beds=max_beds,
            property_types=property_types,
            sale_type=sale_type,
            keywords=keywords,
            ber_ratings=ber_ratings,
            sort_by=sort_by,
            sort_dir=sort_dir,
            lat=lat,
            lng=lng,
            radius_km=radius_km,
            eligible_only=eligible_only,
            min_eligible_grants_total=min_eligible_grants_total,
        )
    except PropertyValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get("/{property_id}", response_model=PropertyResponse)
def get_property(property_id: str, db: Session = Depends(get_db_session)):
    """Get a single property by ID with full details."""
    repo = PropertyRepository(db)
    try:
        return get_property_payload(repo=repo, property_id=property_id)
    except PropertyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Property not found") from exc


@router.get("/{property_id}/price-history")
def get_price_history(
    property_id: str = Path(..., min_length=36, max_length=36),
    limit: int = Query(100, ge=1, le=1000, description="Max number of history entries"),
    db: Session = Depends(get_db_session),
):
    """Get price history for a property."""
    repo = PriceHistoryRepository(db)
    return get_price_history_payload(repo=repo, property_id=property_id, limit=limit)


@router.get("/{property_id}/timeline", response_model=list[PropertyTimelineEventResponse])
def get_timeline(
    property_id: str = Path(..., min_length=36, max_length=36),
    limit: int = Query(100, ge=1, le=1000, description="Max number of timeline entries"),
    db: Session = Depends(get_db_session),
):
    """Get unified timeline events for a property with provenance and confidence."""
    repo = PropertyTimelineRepository(db)
    return get_timeline_payload(repo=repo, property_id=property_id, limit=limit)


@router.get("/{property_id}/similar")
def get_similar(
    property_id: str,
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db_session),
):
    """Find similar properties based on location, price, and type."""
    repo = PropertyRepository(db)
    try:
        return get_similar_payload(repo=repo, property_id=property_id, limit=limit)
    except PropertyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Property not found") from exc


@router.get("/{property_id}/intelligence")
def get_intelligence(
    property_id: str = Path(..., min_length=1, max_length=36),
    db: Session = Depends(get_db_session),
):
    """Consolidated property intelligence: listing + price history + timeline + RAG documents."""
    try:
        return get_intelligence_payload(
            property_repo=PropertyRepository(db),
            price_history_repo=PriceHistoryRepository(db),
            timeline_repo=PropertyTimelineRepository(db),
            document_repo=PropertyDocumentRepository(db),
            property_id=property_id,
        )
    except PropertyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Property not found") from exc


@router.get("/{property_id}/brief")
def get_brief(
    property_id: str = Path(..., min_length=1, max_length=36),
    db: Session = Depends(get_db_session),
):
    """Generate a structured decision brief for a single property.

    Combines listing detail, price history, AI enrichment, and risk flags
    suitable for saving, sharing, or printing.
    """
    try:
        return get_brief_payload(
            property_repo=PropertyRepository(db),
            price_history_repo=PriceHistoryRepository(db),
            timeline_repo=PropertyTimelineRepository(db),
            document_repo=PropertyDocumentRepository(db),
            property_id=property_id,
        )
    except PropertyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Property not found") from exc
