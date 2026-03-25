from datetime import date
from types import SimpleNamespace

from packages.sold.service import (
    build_sold_filters,
    list_sold_payload,
    nearby_sold_payload,
    sold_stats_payload,
)


class _FakeSoldRepo:
    def __init__(self, items=None, total=0, stats=None):
        self._items = items or []
        self._total = total
        self._stats = stats or []
        self.last_filters = None
        self.last_nearby = None
        self.last_stats = None

    def list_sold(self, filters):
        self.last_filters = filters
        return self._items, self._total

    def get_nearby_sold(self, *, lat, lng, radius_km, limit):
        self.last_nearby = {
            "lat": lat,
            "lng": lng,
            "radius_km": radius_km,
            "limit": limit,
        }
        return self._items

    def get_stats_by_county(self, *, county, group_by):
        self.last_stats = {"county": county, "group_by": group_by}
        return self._stats


class TestBuildSoldFilters:
    def test_builds_year_range_dates(self):
        filters = build_sold_filters(
            page=2,
            size=10,
            county="Dublin",
            min_price=250000,
            max_price=500000,
            address_contains="Main",
            min_year=2020,
            max_year=2021,
            lat=53.34,
            lng=-6.26,
            radius_km=2.5,
        )

        assert filters.date_from == date(2020, 1, 1)
        assert filters.date_to == date(2021, 12, 31)
        assert filters.address_contains == "Main"
        assert filters.page == 2
        assert filters.per_page == 10


class TestSoldPayloads:
    def test_list_payload_serializes_items_and_pagination(self):
        sold = SimpleNamespace(
            id="sold-1",
            address="Main St",
            county="Dublin",
            price=320000,
            sale_date=date(2024, 5, 10),
            is_new=False,
            is_full_market_price=True,
            property_size_description="110 m2",
            latitude=53.34,
            longitude=-6.26,
        )
        repo = _FakeSoldRepo(items=[sold], total=21)

        payload = list_sold_payload(
            repo=repo,
            page=2,
            size=20,
            county=None,
            min_price=None,
            max_price=None,
            address_contains="Main",
            min_year=None,
            max_year=None,
            lat=None,
            lng=None,
            radius_km=None,
        )

        assert payload["total"] == 21
        assert payload["pages"] == 2
        assert payload["items"][0]["id"] == "sold-1"
        assert payload["items"][0]["sale_date"] == "2024-05-10"
        assert repo.last_filters is not None
        assert repo.last_filters.address_contains == "Main"

    def test_nearby_payload_preserves_endpoint_shape(self):
        sold = SimpleNamespace(
            id="sold-2",
            address="2 Main St",
            county="Cork",
            price=280000,
            sale_date=date(2023, 3, 9),
            is_new=True,
            is_full_market_price=False,
            property_size_description=None,
            latitude=51.9,
            longitude=-8.47,
        )
        repo = _FakeSoldRepo(items=[sold])

        payload = nearby_sold_payload(repo=repo, lat=51.9, lng=-8.47, radius_km=5.0, limit=10)

        assert len(payload) == 1
        assert payload[0] == {
            "id": "sold-2",
            "address": "2 Main St",
            "county": "Cork",
            "price": 280000.0,
            "sale_date": "2023-03-09",
            "latitude": 51.9,
            "longitude": -8.47,
        }
        assert repo.last_nearby == {"lat": 51.9, "lng": -8.47, "radius_km": 5.0, "limit": 10}

    def test_stats_payload_delegates_to_repository(self):
        repo = _FakeSoldRepo(stats=[{"period": "2025-Q1", "avg_price": 350000.0, "count": 12}])

        payload = sold_stats_payload(repo=repo, county="Dublin", group_by="quarter")

        assert payload[0]["period"] == "2025-Q1"
        assert repo.last_stats == {"county": "Dublin", "group_by": "quarter"}
