import asyncio
from types import SimpleNamespace

from packages.normalizer.geocoder import clear_geocode_cache, geocode_address


class TestGeocoderPersistentCache:
    def setup_method(self):
        clear_geocode_cache()

    def teardown_method(self):
        clear_geocode_cache()

    def test_geocode_address_uses_db_cache_before_http(self, monkeypatch):
        class FakeCacheRepo:
            def __init__(self, _db):
                pass

            def record_hit(self, query):
                assert query == "1 main st, co. dublin, ireland"
                return SimpleNamespace(
                    latitude=53.3,
                    longitude=-6.2,
                    display_name="1 Main St, Dublin, Ireland",
                    confidence=0.91,
                    raw_json={"source": "db"},
                )

        monkeypatch.setattr("packages.storage.repositories.GeocodeCacheRepository", FakeCacheRepo)

        class FailIfCalledClient:
            async def __aenter__(self):
                raise AssertionError("HTTP client should not be called on DB cache hit")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: FailIfCalledClient())

        result = asyncio.run(geocode_address("1 Main St", "Dublin", db=object()))

        assert result is not None
        assert result.latitude == 53.3
        assert result.longitude == -6.2
        assert result.raw == {"source": "db"}

    def test_geocode_address_writes_success_to_db_cache(self, monkeypatch):
        upserts = []

        class FakeCacheRepo:
            def __init__(self, _db):
                pass

            def record_hit(self, query):
                assert query == "2 main st, co. cork, ireland"
                return None

            def upsert_success(self, **kwargs):
                upserts.append(kwargs)
                return SimpleNamespace(**kwargs)

        monkeypatch.setattr("packages.storage.repositories.GeocodeCacheRepository", FakeCacheRepo)

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return [
                    {
                        "lat": "51.9",
                        "lon": "-8.47",
                        "display_name": "2 Main St, Cork, Ireland",
                        "importance": 0.77,
                    }
                ]

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, _url, params=None):
                assert params["q"] == "2 Main St, Co. Cork, Ireland"
                return FakeResponse()

        monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: FakeClient())

        result = asyncio.run(geocode_address("2 Main St", "Cork", db=object()))

        assert result is not None
        assert result.latitude == 51.9
        assert result.longitude == -8.47
        assert len(upserts) == 1
        assert upserts[0]["query"] == "2 main st, co. cork, ireland"
        assert upserts[0]["provider"] == "nominatim"