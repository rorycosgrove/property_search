"""Tests for packages.shared.utils."""
from packages.shared.utils import (
    NI_COUNTIES,
    REPUBLIC_COUNTIES,
    content_hash,
    extract_county,
    extract_eircode,
    normalize_address,
    normalize_ber,
    parse_price,
)


class TestNormalizeAddress:
    def test_basic_normalization(self):
        result = normalize_address("  123 Main  Street,  Dublin 2  ")
        assert result == "123 Main Street, Dublin 2"

    def test_removes_extra_whitespace(self):
        result = normalize_address("Apt  5   The   Grove")
        assert result == "Apt 5 The Grove"

    def test_empty_string(self):
        assert normalize_address("") == ""

    def test_none_returns_empty(self):
        assert normalize_address(None) == ""


class TestExtractCounty:
    def test_extract_dublin(self):
        assert extract_county("123 Main Street, Dublin 2") == "Dublin"

    def test_extract_galway(self):
        assert extract_county("Salthill, Co. Galway") == "Galway"

    def test_extract_cork(self):
        assert extract_county("Ballincollig, County Cork") == "Cork"

    def test_no_county(self):
        assert extract_county("Some random address") is None

    def test_county_aliases(self):
        # "Co. Offaly" should work
        result = extract_county("Tullamore, Co. Offaly")
        assert result == "Offaly"


class TestExtractEircode:
    def test_valid_eircode(self):
        result = extract_eircode("123 Main St, Dublin 2 D02 XY45")
        assert result == "D02 XY45"

    def test_no_eircode(self):
        assert extract_eircode("123 Main Street, Dublin") is None

    def test_lowercase_eircode(self):
        result = extract_eircode("Some place a65 f4e2")
        assert result is not None


class TestParsePrice:
    def test_euro_price(self):
        assert parse_price("€350,000") == 350000

    def test_price_with_spaces(self):
        assert parse_price("€ 1,250,000") == 1250000

    def test_plain_number(self):
        assert parse_price("275000") == 275000

    def test_none_returns_none(self):
        assert parse_price(None) is None

    def test_poa(self):
        assert parse_price("POA") is None

    def test_price_on_application(self):
        assert parse_price("Price on application") is None


class TestNormalizeBER:
    def test_valid_ber(self):
        assert normalize_ber("A1") == "A1"
        assert normalize_ber("b2") == "B2"
        assert normalize_ber("G") == "G"

    def test_exempt(self):
        assert normalize_ber("exempt") == "Exempt"

    def test_invalid(self):
        assert normalize_ber("XYZ") is None


class TestContentHash:
    def test_deterministic(self):
        h1 = content_hash("test", 123, 3, "source1")
        h2 = content_hash("test", 123, 3, "source1")
        assert h1 == h2

    def test_different_inputs(self):
        h1 = content_hash("a", 100, 2, "source1")
        h2 = content_hash("b", 200, 3, "source2")
        assert h1 != h2


class TestCountyLists:
    def test_republic_has_26(self):
        assert len(REPUBLIC_COUNTIES) == 26

    def test_ni_has_6(self):
        assert len(NI_COUNTIES) == 6

    def test_dublin_in_republic(self):
        assert "Dublin" in REPUBLIC_COUNTIES
