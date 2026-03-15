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
