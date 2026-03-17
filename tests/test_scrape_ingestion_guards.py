from datetime import date, datetime

from apps.worker.tasks import _parse_ppr_sale_date
from packages.sources.base import RawListing
from packages.sources.daft import DaftAdapter
from packages.sources.myhome import MyHomeAdapter
from packages.sources.propertypal import PropertyPalAdapter


class TestPprDateParsing:
    def test_parse_ppr_sale_date_ddmmyyyy(self):
        parsed = _parse_ppr_sale_date("07/03/2026")
        assert parsed == date(2026, 3, 7)

    def test_parse_ppr_sale_date_iso(self):
        parsed = _parse_ppr_sale_date("2026-03-07")
        assert parsed == date(2026, 3, 7)

    def test_parse_ppr_sale_date_datetime(self):
        parsed = _parse_ppr_sale_date(datetime(2026, 3, 7, 12, 0, 0))
        assert parsed == date(2026, 3, 7)

    def test_parse_ppr_sale_date_invalid(self):
        assert _parse_ppr_sale_date("not-a-date") is None


class TestAdapterParseGuards:
    def test_myhome_parse_skips_missing_required_fields(self):
        adapter = MyHomeAdapter()
        raw = RawListing(raw_data={"Address": "", "DisplayAddress": "", "BrochureUrl": ""}, source_url="")
        assert adapter.parse_listing(raw) is None

    def test_propertypal_parse_skips_missing_required_fields(self):
        adapter = PropertyPalAdapter()
        raw = RawListing(raw_data={"displayAddress": "", "path": ""}, source_url="")
        assert adapter.parse_listing(raw) is None

    def test_daft_parse_skips_missing_required_fields(self):
        adapter = DaftAdapter()
        raw = RawListing(raw_data={"title": "", "seoFriendlyPath": ""}, source_url="")
        assert adapter.parse_listing(raw) is None

    def test_daft_parse_normalizes_url_and_uses_id_from_path(self):
        adapter = DaftAdapter()
        raw = RawListing(
            raw_data={
                "title": "Lighthouse, Ballydesmond, Co. Cork",
                "seoFriendlyPath": "/for-sale/house-lighthouse-ballydesmond-co-cork/6437639/?search=abc",
                "id": "",
                "price": "EUR 250,000",
            },
            source_url="https://www.daft.ie/for-sale/house-lighthouse-ballydesmond-co-cork/6437639?utm=tracking",
        )

        parsed = adapter.parse_listing(raw)

        assert parsed is not None
        assert parsed.external_id == "6437639"
        assert parsed.url == "https://www.daft.ie/for-sale/house-lighthouse-ballydesmond-co-cork/6437639"

    def test_daft_parse_skips_invalid_listing_path_without_id(self):
        adapter = DaftAdapter()
        raw = RawListing(
            raw_data={
                "title": "Some Address, Co. Cork",
                "seoFriendlyPath": "/for-sale/house-some-address-co-cork",
                "price": "EUR 200,000",
            },
            source_url="https://www.daft.ie/for-sale/house-some-address-co-cork",
        )

        assert adapter.parse_listing(raw) is None

    def test_daft_parse_preserves_api_id_when_payload_and_url_id_differ(self):
        adapter = DaftAdapter()
        raw = RawListing(
            raw_data={
                "title": "Mismatch Address, Co. Cork",
                "seoFriendlyPath": "/for-sale/house-mismatch-address-co-cork/6437639",
                "id": "16437639",
                "price": "EUR 200,000",
            },
            source_url="https://www.daft.ie/for-sale/house-mismatch-address-co-cork/6437639",
        )

        parsed = adapter.parse_listing(raw)

        assert parsed is not None
        assert parsed.external_id == "16437639"
        assert parsed.raw_data["url_listing_id"] == "6437639"
