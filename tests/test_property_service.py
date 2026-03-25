from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from packages.properties.service import (
    PropertyNotFoundError,
    PropertyValidationError,
    build_property_filters,
    get_price_history_payload,
    get_property_payload,
    get_sold_comps_payload,
    get_timeline_payload,
    list_properties_payload,
    property_to_dict,
)


class _FakePropertyRepo:
    def __init__(self, prop=None, items=None, total=0):
        self._prop = prop
        self._items = items or []
        self._total = total
        self.last_filters = None

    def get_by_id(self, _property_id):
        return self._prop

    def list_properties(self, filters):
        self.last_filters = filters
        return self._items, self._total


class _FakePriceHistoryRepo:
    def __init__(self, history):
        self._history = history

    def get_for_property(self, _property_id):
        return self._history


class _FakeTimelineRepo:
    def __init__(self, history):
        self._history = history

    def list_for_property(self, _property_id, limit=100):
        return self._history[:limit]


class _FakeSoldRepo:
    def __init__(self, nearby=None, fuzzy=None):
        self._nearby = nearby or []
        self._fuzzy = fuzzy or []
        self.last_nearby_args = None
        self.last_fuzzy_args = None

    def get_nearby_sold(self, **kwargs):
        self.last_nearby_args = kwargs
        return self._nearby

    def get_confident_comparable_sold(self, **kwargs):
        self.last_fuzzy_args = kwargs
        return self._fuzzy


class TestBuildPropertyFilters:
    def test_raises_when_min_price_exceeds_max_price(self):
        with pytest.raises(PropertyValidationError, match="min_price"):
            build_property_filters(
                page=1,
                size=20,
                county=None,
                min_price=500000,
                max_price=400000,
                min_beds=None,
                max_beds=None,
                property_types=None,
                sale_type=None,
                keywords=None,
                ber_ratings=None,
                sort_by="created_at",
                sort_dir="desc",
                lat=None,
                lng=None,
                radius_km=None,
                eligible_only=False,
                min_eligible_grants_total=None,
            )

    def test_raises_when_geospatial_args_incomplete(self):
        with pytest.raises(PropertyValidationError, match="must all be provided"):
            build_property_filters(
                page=1,
                size=20,
                county=None,
                min_price=None,
                max_price=None,
                min_beds=None,
                max_beds=None,
                property_types=None,
                sale_type=None,
                keywords=None,
                ber_ratings=None,
                sort_by="created_at",
                sort_dir="desc",
                lat=53.3,
                lng=None,
                radius_km=5.0,
                eligible_only=False,
                min_eligible_grants_total=None,
            )


class TestPropertyPayloads:
    def test_get_property_payload_raises_for_missing_property(self):
        repo = _FakePropertyRepo(prop=None)
        with pytest.raises(PropertyNotFoundError):
            get_property_payload(repo=repo, property_id="missing")

    def test_list_properties_payload_builds_filters_and_paginates(self):
        prop = SimpleNamespace(
            id="p-1",
            title="House",
            description="desc",
            url="https://example.com/p-1",
            address="Main St",
            county="Dublin",
            eircode=None,
            price=320000,
            property_type="house",
            sale_type="sale",
            bedrooms=3,
            bathrooms=2,
            floor_area_sqm=110,
            ber_rating="B2",
            images=[],
            features={},
            latitude=None,
            longitude=None,
            status="active",
            source_id="s-1",
            external_id="x-1",
            content_hash="abc",
            first_listed_at=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            enrichment=None,
            price_history=[],
        )
        repo = _FakePropertyRepo(items=[prop], total=1)

        payload = list_properties_payload(
            repo=repo,
            page=1,
            size=20,
            county="Dublin",
            min_price=200000,
            max_price=500000,
            min_beds=2,
            max_beds=4,
            property_types="house,apartment",
            sale_type="sale",
            keywords="Main",
            ber_ratings="A1,B2",
            sort_by="created_at",
            sort_dir="desc",
            lat=None,
            lng=None,
            radius_km=None,
            eligible_only=False,
            min_eligible_grants_total=None,
        )

        assert payload["total"] == 1
        assert payload["pages"] == 1
        assert repo.last_filters is not None
        assert repo.last_filters.property_types == ["house", "apartment"]
        assert repo.last_filters.sale_type == "sale"
        assert repo.last_filters.keywords == ["Main"]
        assert repo.last_filters.ber_ratings == ["A1", "B2"]

    def test_property_to_dict_includes_price_history(self):
        history_point = SimpleNamespace(
            price=300000,
            price_change=-10000,
            price_change_pct=-3.2,
            recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        prop = SimpleNamespace(
            id="p-2",
            title="Flat",
            description=None,
            url="https://example.com/p-2",
            address="2 Main St",
            county="Cork",
            eircode=None,
            price=290000,
            property_type="apartment",
            sale_type="sale",
            bedrooms=2,
            bathrooms=1,
            floor_area_sqm=70,
            ber_rating="C1",
            images=[],
            features={},
            latitude=None,
            longitude=None,
            status="active",
            source_id="s-2",
            external_id="x-2",
            content_hash="def",
            first_listed_at=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            enrichment=None,
            price_history=[history_point],
        )

        payload = property_to_dict(prop)
        assert payload["id"] == "p-2"
        assert len(payload["price_history"]) == 1
        assert payload["price_history"][0]["price"] == 300000.0

    def test_get_price_history_payload_limits_results(self):
        history = [
            SimpleNamespace(
                id=f"h-{idx}",
                price=300000 + idx,
                price_change=None,
                price_change_pct=None,
                recorded_at=datetime(2026, 1, idx + 1, tzinfo=UTC),
            )
            for idx in range(3)
        ]
        repo = _FakePriceHistoryRepo(history)

        payload = get_price_history_payload(repo=repo, property_id="p-1", limit=2)

        assert len(payload) == 2
        assert payload[0]["id"] == "h-1"
        assert payload[1]["id"] == "h-2"

    def test_get_timeline_payload_includes_provenance(self):
        timeline = [
            SimpleNamespace(
                id="t-1",
                event_type="asking_price_changed",
                occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
                price=310000,
                price_change=-5000,
                price_change_pct=-1.59,
                source_id="s-1",
                adapter_name="daft",
                source_url="https://example.com/p-1",
                detection_method="worker_scrape_price_diff",
                confidence_score=0.95,
                dedup_key="price:310000.00",
                evidence={"raw_id": "abc"},
                metadata_json={"source_name": "Daft.ie"},
            ),
            SimpleNamespace(
                id="t-2",
                event_type="listing_discovered",
                occurred_at=datetime(2026, 1, 2, tzinfo=UTC),
                price=None,
                price_change=None,
                price_change_pct=None,
                source_id="s-1",
                adapter_name="daft",
                source_url="https://example.com/p-1",
                detection_method="worker_new_listing",
                confidence_score=0.85,
                dedup_key="listing:x-1",
                evidence={},
                metadata_json={"status": "new"},
            ),
        ]

        repo = _FakeTimelineRepo(timeline)
        payload = get_timeline_payload(repo=repo, property_id="p-1", limit=1)

        assert len(payload) == 1
        assert payload[0]["id"] == "t-1"
        assert payload[0]["event_type"] == "asking_price_changed"
        assert payload[0]["source_id"] == "s-1"
        assert payload[0]["adapter_name"] == "daft"
        assert payload[0]["confidence_score"] == pytest.approx(0.95)
        assert payload[0]["metadata"]["source_name"] == "Daft.ie"

    def test_get_sold_comps_payload_uses_geo_strategy_when_coordinates_present(self):
        prop = SimpleNamespace(
            id="p-geo",
            address="1 Main St",
            county="Dublin",
            fuzzy_address_hash="h1",
            latitude=53.3,
            longitude=-6.2,
        )
        sold = SimpleNamespace(
            id="s-1",
            address="2 Main St",
            county="Dublin",
            price=300000,
            sale_date=datetime(2025, 1, 1, tzinfo=UTC).date(),
            latitude=53.31,
            longitude=-6.21,
        )
        property_repo = _FakePropertyRepo(prop=prop)
        sold_repo = _FakeSoldRepo(nearby=[sold])

        payload = get_sold_comps_payload(
            property_repo=property_repo,
            sold_repo=sold_repo,
            property_id="p-geo",
            limit=5,
            min_similarity=0.86,
        )

        assert payload["strategy"] == "geo_radius"
        assert payload["items"][0]["match_confidence"] == "high"
        assert sold_repo.last_nearby_args is not None
        assert sold_repo.last_fuzzy_args is None

    def test_get_sold_comps_payload_uses_address_strategy_without_coordinates(self):
        prop = SimpleNamespace(
            id="p-fuzzy",
            address="1 Main St",
            county="Dublin",
            fuzzy_address_hash="h1",
            latitude=None,
            longitude=None,
        )
        comps = [
            {
                "id": "s-2",
                "address": "1 Main Street",
                "county": "Dublin",
                "price": 320000.0,
                "sale_date": "2025-02-10",
                "match_method": "fuzzy_hash_county_address_similarity",
                "match_score": 0.94,
                "match_confidence": "medium",
            }
        ]
        property_repo = _FakePropertyRepo(prop=prop)
        sold_repo = _FakeSoldRepo(fuzzy=comps)

        payload = get_sold_comps_payload(
            property_repo=property_repo,
            sold_repo=sold_repo,
            property_id="p-fuzzy",
            limit=5,
            min_similarity=0.9,
        )

        assert payload["strategy"] == "address_fuzzy"
        assert payload["items"][0]["match_method"] == "fuzzy_hash_county_address_similarity"
        assert sold_repo.last_fuzzy_args["min_similarity"] == 0.9
        assert sold_repo.last_nearby_args is None
