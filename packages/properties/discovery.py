"""Discovery signal engine — detects and surfaces actionable property signals.

Produces a ranked feed of cards for the UI, based on:
  price_drop   — active properties where the most recent price history entry shows a >= 5% drop
  high_value   — properties with AI enrichment value_score >= 7.5
  stale        — active properties listed > 90 days with no price movement
  new_listing  — properties listed in the last 7 days with confirmed data
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session, joinedload

from packages.storage.models import (
    LLMEnrichment,
    Property,
    PropertyPriceHistory,
)

# ── Thresholds ─────────────────────────────────────────────────────────────

PRICE_DROP_THRESHOLD_PCT = -5.0   # negative = price fell
HIGH_VALUE_SCORE_THRESHOLD = 7.5
STALE_LISTING_DAYS = 90
NEW_LISTING_DAYS = 7
SLOT_LIMIT = 6   # cards per signal type before trimming


# ── Helpers ────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _prop_image(prop: Property) -> str | None:
    if prop.images and len(prop.images) > 0:
        img = prop.images[0]
        return img if isinstance(img, str) else img.get("url") if isinstance(img, dict) else None
    return None


def _base_card(signal_type: str, severity: str, prop: Property) -> dict[str, Any]:
    return {
        "signal_type": signal_type,
        "severity": severity,
        "property_id": str(prop.id),
        "title": prop.title or prop.address,
        "address": prop.address,
        "county": prop.county,
        "price": float(prop.price) if prop.price else None,
        "url": prop.url,
        "image_url": _prop_image(prop),
        "status": prop.status,
        "created_at": prop.created_at.isoformat() if prop.created_at else None,
    }


# ── Signal queries ─────────────────────────────────────────────────────────

def _price_drop_cards(db: Session, limit: int) -> list[dict[str, Any]]:
    """Properties where the most recent price history entry records a >= 5% fall."""
    # Subquery: latest recorded_at per property
    latest_sq = (
        select(
            PropertyPriceHistory.property_id,
            func.max(PropertyPriceHistory.recorded_at).label("latest_at"),
        )
        .group_by(PropertyPriceHistory.property_id)
        .subquery("latest_ph")
    )

    rows = (
        db.execute(
            select(Property, PropertyPriceHistory)
            .join(
                latest_sq,
                Property.id == latest_sq.c.property_id,
            )
            .join(
                PropertyPriceHistory,
                and_(
                    PropertyPriceHistory.property_id == latest_sq.c.property_id,
                    PropertyPriceHistory.recorded_at == latest_sq.c.latest_at,
                ),
            )
            .where(
                and_(
                    Property.status.in_(["active", "price_changed"]),
                    PropertyPriceHistory.price_change_pct <= PRICE_DROP_THRESHOLD_PCT,
                )
            )
            .order_by(PropertyPriceHistory.price_change_pct)  # most negative first
            .limit(limit)
        )
        .all()
    )

    cards = []
    for prop, ph in rows:
        pct = float(ph.price_change_pct) if ph.price_change_pct is not None else 0.0
        change_abs = float(ph.price_change) if ph.price_change else None
        prev_price = (float(prop.price) - change_abs) if (prop.price and change_abs) else None
        card = _base_card("price_drop", "high" if pct <= -10 else "medium", prop)
        card["headline"] = f"Price dropped {abs(pct):.0f}% — now €{float(prop.price):,.0f}" if prop.price else "Price reduced"
        card["detail"] = (
            f"Reduced from €{prev_price:,.0f} ({abs(pct):.1f}% fall)." if prev_price else f"Price fell {abs(pct):.1f}%."
        )
        card["_sort_key"] = abs(pct)
        cards.append(card)
    return cards


def _high_value_cards(db: Session, limit: int) -> list[dict[str, Any]]:
    """Properties with AI enrichment value_score >= threshold."""
    rows = (
        db.execute(
            select(Property, LLMEnrichment)
            .join(LLMEnrichment, Property.id == LLMEnrichment.property_id)
            .where(
                and_(
                    Property.status.in_(["active", "price_changed", "new"]),
                    LLMEnrichment.value_score >= HIGH_VALUE_SCORE_THRESHOLD,
                )
            )
            .order_by(desc(LLMEnrichment.value_score))
            .limit(limit)
        )
        .all()
    )

    cards = []
    for prop, enr in rows:
        score = float(enr.value_score)
        card = _base_card("high_value", "high" if score >= 9 else "medium", prop)
        card["headline"] = f"Strong value signal — AI score {score:.1f}/10"
        card["detail"] = enr.value_reasoning or (enr.summary or "")[:160] if enr.value_reasoning or enr.summary else "Atlas rates this property as exceptional value."
        card["value_score"] = score
        card["_sort_key"] = score
        cards.append(card)
    return cards


def _stale_listing_cards(db: Session, limit: int) -> list[dict[str, Any]]:
    """Active listings on the market > STALE_LISTING_DAYS with no price reduction."""
    cutoff = _utcnow() - timedelta(days=STALE_LISTING_DAYS)

    # Properties listed before cutoff still active, with zero recent price changes
    recently_changed_sq = (
        select(PropertyPriceHistory.property_id)
        .where(PropertyPriceHistory.recorded_at >= cutoff)
        .where(PropertyPriceHistory.price_change_pct.isnot(None))
        .where(PropertyPriceHistory.price_change_pct != 0)
        .distinct()
        .subquery("recently_changed")
    )

    rows = (
        db.execute(
            select(Property)
            .where(
                and_(
                    Property.status == "active",
                    Property.created_at <= cutoff,
                    ~Property.id.in_(select(recently_changed_sq.c.property_id)),
                )
            )
            .order_by(Property.created_at)   # oldest first
            .limit(limit)
            .options(joinedload(Property.enrichment))
        )
        .scalars()
        .unique()
        .all()
    )

    cards = []
    for prop in rows:
        days_on = (_utcnow() - prop.created_at).days if prop.created_at else STALE_LISTING_DAYS
        card = _base_card("stale", "medium" if days_on < 120 else "low", prop)
        card["headline"] = f"On the market {days_on} days — no price move"
        card["detail"] = f"Listed {days_on} days ago with no reduction. May indicate room to negotiate."
        card["days_on_market"] = days_on
        card["_sort_key"] = -days_on   # show moderately stale first, avoid very long stale being confusing
        cards.append(card)
    return cards


def _new_listing_cards(db: Session, limit: int) -> list[dict[str, Any]]:
    """Recently listed properties with good data completeness."""
    cutoff = _utcnow() - timedelta(days=NEW_LISTING_DAYS)

    rows = (
        db.execute(
            select(Property)
            .where(
                and_(
                    Property.status.in_(["new", "active"]),
                    Property.created_at >= cutoff,
                    Property.price.isnot(None),
                    Property.bedrooms.isnot(None),
                )
            )
            .order_by(desc(Property.created_at))
            .limit(limit)
            .options(joinedload(Property.enrichment))
        )
        .scalars()
        .unique()
        .all()
    )

    cards = []
    for prop in rows:
        hours_ago = int((_utcnow() - prop.created_at).total_seconds() / 3600) if prop.created_at else 0
        age_str = f"{hours_ago}h ago" if hours_ago < 48 else f"{hours_ago // 24}d ago"
        card = _base_card("new_listing", "medium", prop)
        card["headline"] = f"New listing — added {age_str}"
        card["detail"] = (
            f"{prop.bedrooms}-bed {prop.property_type or 'property'} in {prop.county or 'unknown county'}"
            + (f", BER {prop.ber_rating}" if prop.ber_rating else "")
        )
        card["_sort_key"] = prop.created_at.timestamp() if prop.created_at else 0
        cards.append(card)
    return cards


# ── Public API ─────────────────────────────────────────────────────────────

def get_discovery_feed(db: Session, *, limit: int = 20) -> list[dict[str, Any]]:
    """Return a ranked list of discovery signal cards, up to *limit* items.

    Each card has shape::

        {
            signal_type: "price_drop" | "high_value" | "stale" | "new_listing",
            severity:    "high" | "medium" | "low",
            property_id: str,
            title:       str,
            address:     str,
            county:      str | None,
            price:       float | None,
            url:         str,
            image_url:   str | None,
            status:      str,
            created_at:  str,
            headline:    str,
            detail:      str,
            # signal-specific extra keys
        }
    """
    slot = max(SLOT_LIMIT, limit // 4 + 2)

    all_cards: list[dict[str, Any]] = []
    all_cards.extend(_price_drop_cards(db, slot))
    all_cards.extend(_high_value_cards(db, slot))
    all_cards.extend(_stale_listing_cards(db, slot))
    all_cards.extend(_new_listing_cards(db, slot))

    # Sort descending by _sort_key, strip internal key
    all_cards.sort(key=lambda c: c.get("_sort_key", 0), reverse=True)
    for card in all_cards:
        card.pop("_sort_key", None)

    return all_cards[:limit]
