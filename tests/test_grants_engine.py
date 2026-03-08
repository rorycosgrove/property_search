"""Tests for grant eligibility evaluation logic."""

from types import SimpleNamespace

from packages.grants.engine import _evaluate_single


def test_evaluate_single_returns_eligible_when_rules_pass() -> None:
    grant = SimpleNamespace(
        max_amount=5000,
        country="IE",
        region=None,
        eligibility_rules={
            "max_price": 550000,
            "min_bedrooms": 2,
            "property_types": ["house", "apartment"],
            "min_ber": "C1",
        },
    )
    prop = SimpleNamespace(
        county="Dublin",
        price=450000,
        bedrooms=3,
        property_type="house",
        ber_rating="B2",
    )

    status, reason, benefit, metadata = _evaluate_single(grant, prop)

    assert status == "eligible"
    assert "passed" in reason.lower()
    assert benefit == 5000.0
    assert isinstance(metadata.get("checks"), list)


def test_evaluate_single_returns_ineligible_when_price_too_high() -> None:
    grant = SimpleNamespace(
        max_amount=10000,
        country="IE",
        region=None,
        eligibility_rules={"max_price": 300000},
    )
    prop = SimpleNamespace(
        county="Galway",
        price=450000,
        bedrooms=2,
        property_type="house",
        ber_rating="C2",
    )

    status, reason, benefit, _metadata = _evaluate_single(grant, prop)

    assert status == "ineligible"
    assert "exceeds" in reason.lower()
    assert benefit is None
