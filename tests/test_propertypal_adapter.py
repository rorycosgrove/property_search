from __future__ import annotations

import pytest
import httpx

from packages.sources.propertypal import PropertyPalAdapter


class _ForbiddenPropertyPalClient:
    def __init__(self, *args, **kwargs):
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, _url):
        self.calls += 1
        request = httpx.Request("GET", "https://www.propertypal.com/property-for-sale/republic-of-ireland")
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)


@pytest.mark.asyncio
async def test_fetch_listings_stops_area_after_first_403(monkeypatch):
    adapter = PropertyPalAdapter()

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("packages.sources.propertypal.asyncio.sleep", _no_sleep)
    monkeypatch.setattr("packages.sources.propertypal.httpx.AsyncClient", _ForbiddenPropertyPalClient)

    listings = await adapter.fetch_listings(
        {
            "areas": ["republic-of-ireland"],
            "max_pages": 5,
        }
    )

    assert listings == []