from __future__ import annotations

import pytest
import httpx

from packages.sources.daft import DaftAdapter, DAFT_API_URL


class _FakeClient:
    def __init__(self, responses):
        self._responses = responses
        self.calls = 0

    async def post(self, _url, json):
        self.calls += 1
        action = self._responses.pop(0)
        return action(json)


class _PagedAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, _url, json):
        self.calls += 1
        offset = int(json["paging"]["from"])
        page = offset // 20
        payload = {
            "listings": [
                {"listing": {"id": page * 20 + idx + 1, "seoFriendlyPath": f"/for-sale/test-{page}-{idx}/{page * 20 + idx + 1}"}}
                for idx in range(20)
            ],
            "paging": {"totalPages": 50},
        }
        return httpx.Response(200, request=httpx.Request("POST", DAFT_API_URL), json=payload)


class _ForbiddenFirstPageAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, _url, json):
        self.calls += 1
        request = httpx.Request("POST", DAFT_API_URL)
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)


def _http_error(status_code: int) -> callable:
    def _build(_json):
        request = httpx.Request("POST", DAFT_API_URL)
        response = httpx.Response(status_code=status_code, request=request)
        raise httpx.HTTPStatusError("status error", request=request, response=response)

    return _build


def _ok_with_payload(payload: dict) -> callable:
    def _build(_json):
        return httpx.Response(200, request=httpx.Request("POST", DAFT_API_URL), json=payload)

    return _build


@pytest.mark.asyncio
async def test_fetch_page_with_retries_recovers_after_429(monkeypatch):
    adapter = DaftAdapter()
    client = _FakeClient(
        [
            _http_error(429),
            _ok_with_payload({"listings": [{"listing": {"id": 123}}], "paging": {"totalPages": 1}}),
        ]
    )

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("packages.sources.daft.asyncio.sleep", _no_sleep)

    result = await adapter._fetch_page_with_retries(
        client=client,
        payload={"test": True},
        area="cork",
        page=0,
        offset=0,
        max_retries=2,
    )

    assert result is not None
    assert len(result["listings"]) == 1
    assert client.calls == 2


@pytest.mark.asyncio
async def test_fetch_page_with_retries_does_not_retry_404(monkeypatch):
    adapter = DaftAdapter()
    client = _FakeClient([_http_error(404)])

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("packages.sources.daft.asyncio.sleep", _no_sleep)

    result = await adapter._fetch_page_with_retries(
        client=client,
        payload={"test": True},
        area="cork",
        page=0,
        offset=0,
        max_retries=3,
    )

    assert result is None
    assert client.calls == 1


@pytest.mark.asyncio
async def test_fetch_listings_stops_area_after_first_403(monkeypatch):
    adapter = DaftAdapter()

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("packages.sources.daft.asyncio.sleep", _no_sleep)
    monkeypatch.setattr("packages.sources.daft.httpx.AsyncClient", _ForbiddenFirstPageAsyncClient)

    listings = await adapter.fetch_listings(
        {
            "areas": ["dublin"],
            "max_pages": 5,
            "max_retries": 2,
        }
    )

    assert listings == []


def test_extract_listing_id_only_for_canonical_for_sale_paths():
    adapter = DaftAdapter()

    assert adapter._extract_listing_id_from_url(
        "https://www.daft.ie/for-sale/house-lighthouse-ballydesmond-co-cork/6437639?utm=1"
    ) == "6437639"
    assert adapter._extract_listing_id_from_url("https://www.daft.ie/property-for-sale/cork") is None
    assert adapter._extract_listing_id_from_url("https://www.daft.ie/for-rent/apartment-dublin/1234") is None


def test_listing_matches_identifier_accepts_api_and_url_ids():
    raw_data = {"id": "16437639", "url_listing_id": "6437639"}
    source_url = "https://www.daft.ie/for-sale/house-lighthouse-ballydesmond-co-cork/6437639"

    assert DaftAdapter.listing_matches_identifier(
        raw_data=raw_data,
        source_url=source_url,
        external_id="16437639",
    ) is True
    assert DaftAdapter.listing_matches_identifier(
        raw_data=raw_data,
        source_url=source_url,
        external_id="6437639",
    ) is True


@pytest.mark.asyncio
async def test_fetch_listings_history_tail_extends_only_once(monkeypatch):
    adapter = DaftAdapter()

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("packages.sources.daft.asyncio.sleep", _no_sleep)
    monkeypatch.setattr("packages.sources.daft.httpx.AsyncClient", _PagedAsyncClient)

    listings = await adapter.fetch_listings(
        {
            "areas": ["dublin"],
            "max_pages": 2,
            "tail_pass_pages": 0,
            "history_tail_pass_pages": 1,
            "history_tail_trigger_min_new_ids": 1,
            "recent_listing_ids": [],
        }
    )

    assert len(listings) == 60
