from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from packages.sources.ppr import PPRAdapter


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self._content = kwargs.pop("_content", None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, _url):
        return _FakeResponse(self._content)


def _make_zip_with_csv() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            "PPR.csv",
            "Address,County,Price (€),Date of Sale (dd/mm/yyyy),Property Size Description\n"
            "1 Main Street,Dublin,350000,01/03/2026,>= 38 sq metres and < 125 sq metres\n",
        )
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_fetch_listings_reads_ppr_csv_with_stable_dtype_options(monkeypatch):
    adapter = PPRAdapter()
    zip_content = _make_zip_with_csv()
    observed: dict[str, object] = {}

    def _client_factory(*args, **kwargs):
        return _FakeAsyncClient(*args, _content=zip_content, **kwargs)

    real_read_csv = pd.read_csv

    def _read_csv_wrapper(*args, **kwargs):
        observed["encoding"] = kwargs.get("encoding")
        observed["low_memory"] = kwargs.get("low_memory")
        observed["dtype"] = kwargs.get("dtype")
        return real_read_csv(*args, **kwargs)

    monkeypatch.setattr("packages.sources.ppr.httpx.AsyncClient", _client_factory)
    monkeypatch.setattr("packages.sources.ppr.pd.read_csv", _read_csv_wrapper)

    listings = await adapter.fetch_listings({})

    assert len(listings) == 1
    assert observed["encoding"] == "latin-1"
    assert observed["low_memory"] is False
    assert observed["dtype"] == {
        "Property Size Description": "string",
        "Cur Síos ar Mhéid na Maoine": "string",
    }