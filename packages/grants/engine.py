"""Grant eligibility evaluation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.storage.models import GrantProgram, Property
from packages.storage.repositories import GrantProgramRepository, PropertyGrantMatchRepository

_NI_COUNTIES = {
    "antrim",
    "armagh",
    "down",
    "fermanagh",
    "derry",
    "londonderry",
    "tyrone",
}

_BER_ORDER = {
    "A1": 1,
    "A2": 2,
    "A3": 3,
    "B1": 4,
    "B2": 5,
    "B3": 6,
    "C1": 7,
    "C2": 8,
    "C3": 9,
    "D1": 10,
    "D2": 11,
    "E1": 12,
    "E2": 13,
    "F": 14,
    "G": 15,
}


@dataclass
class _CheckResult:
    eligible: bool
    unknown: bool
    reasons: list[str]
    metadata: dict[str, Any]


def evaluate_property_grants(db, property_obj: Property | None = None, property_id: str | None = None) -> list:
    """Evaluate active grant programs for a property and upsert match records."""
    from packages.storage.repositories import PropertyRepository

    if property_obj is None:
        if not property_id:
            return []
        property_obj = PropertyRepository(db).get_by_id(property_id)

    if not property_obj:
        return []

    grant_repo = GrantProgramRepository(db)
    match_repo = PropertyGrantMatchRepository(db)
    grants = grant_repo.list_programs(active_only=True)

    for grant in grants:
        status, reason, estimated_benefit, metadata = _evaluate_single(grant, property_obj)
        match_repo.upsert_match(
            property_id=str(property_obj.id),
            grant_program_id=str(grant.id),
            status=status,
            reason=reason,
            estimated_benefit=estimated_benefit,
            metadata=metadata,
        )

    return match_repo.list_for_property(str(property_obj.id))


def _evaluate_single(grant: GrantProgram, prop: Property) -> tuple[str, str, float | None, dict[str, Any]]:
    rules = grant.eligibility_rules or {}
    checks = [
        _check_country(grant.country, prop.county),
        _check_region(grant.region, prop.county),
        _check_list_rule("counties", prop.county, rules),
        _check_list_rule("property_types", prop.property_type, rules),
        _check_min_numeric("min_price", prop.price, rules),
        _check_max_numeric("max_price", prop.price, rules),
        _check_min_numeric("min_bedrooms", prop.bedrooms, rules),
        _check_max_numeric("max_bedrooms", prop.bedrooms, rules),
        _check_ber_min(prop.ber_rating, rules),
        _check_ber_max(prop.ber_rating, rules),
    ]

    failed = [c for c in checks if not c.eligible and not c.unknown]
    unknown = [c for c in checks if c.unknown]
    metadata: dict[str, Any] = {
        "checks": [c.metadata for c in checks if c.metadata],
    }

    if failed:
        reasons = "; ".join(r for c in failed for r in c.reasons if r)
        return "ineligible", reasons or "Eligibility criteria not met", None, metadata

    if unknown:
        reasons = "; ".join(r for c in unknown for r in c.reasons if r)
        return "unknown", reasons or "Insufficient data for full grant evaluation", None, metadata

    benefit = float(grant.max_amount) if grant.max_amount is not None else None
    return "eligible", "All configured eligibility checks passed", benefit, metadata


def _check_country(country: str | None, county: str | None) -> _CheckResult:
    if not country:
        return _ok()

    normalized_country = country.strip().upper()
    county_norm = (county or "").strip().lower()

    if normalized_country in {"IE", "IRELAND", "ROI"}:
        if county_norm and county_norm in _NI_COUNTIES:
            return _fail("Property appears to be in Northern Ireland")
        return _ok()

    if normalized_country in {"NI", "NIRELAND", "NORTHERN IRELAND"}:
        if not county_norm:
            return _unknown("County is required for NI-only grant checks")
        return _ok() if county_norm in _NI_COUNTIES else _fail("Grant applies to Northern Ireland only")

    return _ok()


def _check_region(region: str | None, county: str | None) -> _CheckResult:
    if not region:
        return _ok()
    if not county:
        return _unknown("County is required for region match")
    return _ok() if region.strip().lower() == county.strip().lower() else _fail("Grant region does not match property county")


def _check_list_rule(rule_key: str, actual_value: Any, rules: dict[str, Any]) -> _CheckResult:
    allowed = _as_str_list(rules.get(rule_key))
    if not allowed:
        return _ok()
    if actual_value is None:
        return _unknown(f"Missing property field for {rule_key}")
    actual = str(actual_value).strip().lower()
    return _ok({"rule": rule_key, "value": actual, "allowed": allowed}) if actual in allowed else _fail(
        f"Property {rule_key.rstrip('s')} '{actual_value}' is not eligible",
        {"rule": rule_key, "value": actual, "allowed": allowed},
    )


def _check_min_numeric(rule_key: str, actual_value: Any, rules: dict[str, Any]) -> _CheckResult:
    threshold = rules.get(rule_key)
    if threshold is None:
        return _ok()
    if actual_value is None:
        return _unknown(f"Missing property field for {rule_key}")
    try:
        actual = float(actual_value)
        minimum = float(threshold)
    except (TypeError, ValueError):
        return _unknown(f"Invalid rule value for {rule_key}")
    if actual < minimum:
        return _fail(
            f"Property value {actual} is below required minimum {minimum} for {rule_key}",
            {"rule": rule_key, "actual": actual, "minimum": minimum},
        )
    return _ok({"rule": rule_key, "actual": actual, "minimum": minimum})


def _check_max_numeric(rule_key: str, actual_value: Any, rules: dict[str, Any]) -> _CheckResult:
    threshold = rules.get(rule_key)
    if threshold is None:
        return _ok()
    if actual_value is None:
        return _unknown(f"Missing property field for {rule_key}")
    try:
        actual = float(actual_value)
        maximum = float(threshold)
    except (TypeError, ValueError):
        return _unknown(f"Invalid rule value for {rule_key}")
    if actual > maximum:
        return _fail(
            f"Property value {actual} exceeds maximum {maximum} for {rule_key}",
            {"rule": rule_key, "actual": actual, "maximum": maximum},
        )
    return _ok({"rule": rule_key, "actual": actual, "maximum": maximum})


def _check_ber_min(ber_rating: str | None, rules: dict[str, Any]) -> _CheckResult:
    required = _normalize_ber(rules.get("min_ber"))
    if not required:
        return _ok()
    actual = _normalize_ber(ber_rating)
    if not actual:
        return _unknown("BER rating is required for min_ber check")
    if _BER_ORDER[actual] > _BER_ORDER[required]:
        return _fail(
            f"BER {actual} is worse than required minimum {required}",
            {"rule": "min_ber", "actual": actual, "required": required},
        )
    return _ok({"rule": "min_ber", "actual": actual, "required": required})


def _check_ber_max(ber_rating: str | None, rules: dict[str, Any]) -> _CheckResult:
    required = _normalize_ber(rules.get("max_ber"))
    if not required:
        return _ok()
    actual = _normalize_ber(ber_rating)
    if not actual:
        return _unknown("BER rating is required for max_ber check")
    if _BER_ORDER[actual] < _BER_ORDER[required]:
        return _fail(
            f"BER {actual} is better than allowed maximum {required}",
            {"rule": "max_ber", "actual": actual, "required": required},
        )
    return _ok({"rule": "max_ber", "actual": actual, "required": required})


def _normalize_ber(value: Any) -> str | None:
    if value is None:
        return None
    ber = str(value).strip().upper()
    return ber if ber in _BER_ORDER else None


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip().lower()] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    return []


def _ok(metadata: dict[str, Any] | None = None) -> _CheckResult:
    return _CheckResult(eligible=True, unknown=False, reasons=[], metadata=metadata or {})


def _fail(reason: str, metadata: dict[str, Any] | None = None) -> _CheckResult:
    return _CheckResult(eligible=False, unknown=False, reasons=[reason], metadata=metadata or {})


def _unknown(reason: str, metadata: dict[str, Any] | None = None) -> _CheckResult:
    return _CheckResult(eligible=False, unknown=True, reasons=[reason], metadata=metadata or {})
