"""Tests for packages.normalizer."""
import pytest
from packages.normalizer.normalizer import PropertyNormalizer
from packages.normalizer.ber import ber_to_score, ber_category, ber_is_better_than, ber_color_hex
from packages.sources.base import NormalizedProperty


class TestPropertyNormalizer:
    def setup_method(self):
        self.normalizer = PropertyNormalizer()

    def test_normalize_basic(self):
        raw = NormalizedProperty(
            url="https://daft.ie/123",
            title="3 Bed Semi-Detached House",
            price=350000,
            address="123 Main Street, Blackrock, Co. Dublin",
            raw_data={},
        )
        result = self.normalizer.normalize(raw)
        assert result is not None
        assert result["price"] == 350000
        assert result["county"] == "Dublin"
        assert "main street" in result["address"].lower()

    def test_normalize_with_beds_in_title(self):
        raw = NormalizedProperty(
            url="https://myhome.ie/456",
            title="4 Bedroom Detached House",
            price=550000,
            address="Galway City, Co. Galway",
            raw_data={},
        )
        result = self.normalizer.normalize(raw)
        assert result is not None
        assert result["bedrooms"] == 4

    def test_normalize_with_ber(self):
        raw = NormalizedProperty(
            url="https://daft.ie/789",
            title="Apartment",
            price=250000,
            address="Cork City, Co. Cork",
            raw_data={"ber_rating": "B2"},
        )
        result = self.normalizer.normalize(raw)
        assert result is not None
        assert result["ber_rating"] == "B2"

    def test_normalize_poa_price(self):
        raw = NormalizedProperty(
            url="https://daft.ie/000",
            title="Luxury Home",
            price_text="Price On Application",
            address="Killiney, Dublin",
            raw_data={},
        )
        result = self.normalizer.normalize(raw)
        assert result is not None
        assert result["price"] is None

    def test_content_hash_is_deterministic(self):
        raw = NormalizedProperty(
            url="https://daft.ie/123",
            title="Test",
            price=100000,
            address="Dublin",
            raw_data={},
        )
        r1 = self.normalizer.normalize(raw)
        r2 = self.normalizer.normalize(raw)
        assert r1["content_hash"] == r2["content_hash"]


class TestBER:
    def test_ber_to_score_a1(self):
        assert ber_to_score("A1") == 0

    def test_ber_to_score_g(self):
        assert ber_to_score("G") == 14

    def test_ber_to_score_invalid(self):
        assert ber_to_score("XYZ") is None

    def test_ber_category(self):
        assert ber_category("A1") == "excellent"
        assert ber_category("B3") == "good"
        assert ber_category("D1") == "below_average"
        assert ber_category("F") == "poor"

    def test_ber_is_better_than(self):
        assert ber_is_better_than("A1", "B1") is True
        assert ber_is_better_than("G", "A1") is False
        assert ber_is_better_than("B2", "B2") is False

    def test_ber_color_hex(self):
        color = ber_color_hex("A1")
        assert color is not None
        assert color.startswith("#")
