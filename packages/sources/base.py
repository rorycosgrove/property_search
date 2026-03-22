"""
Abstract base class for all source adapters.

Every data source (Daft.ie, MyHome.ie, PropertyPal, PPR, RSS) implements
this interface. The adapter system is fully pluggable: new sources are added
by creating a class that inherits from SourceAdapter and registering it
in the SourceRegistry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from packages.shared.schemas import AdapterType


@dataclass
class RawListing:
    """Raw data fetched from a source, before normalization."""
    raw_html: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)
    source_url: str = ""
    fetched_at: datetime | None = None


@dataclass
class NormalizedProperty:
    """
    Normalized property data ready for database insertion.

    This is the common schema that all adapters must produce.
    Maps directly to the Property model columns.
    """
    title: str = ""
    description: str | None = None
    url: str = ""
    address: str = ""
    address_line1: str | None = None
    address_line2: str | None = None
    town: str | None = None
    county: str | None = None
    eircode: str | None = None
    price: float | None = None
    price_text: str | None = None
    property_type: str | None = None
    sale_type: str = "sale"
    bedrooms: int | None = None
    bathrooms: int | None = None
    floor_area_sqm: float | None = None
    ber_rating: str | None = None
    ber_number: str | None = None
    images: list[dict[str, str]] = field(default_factory=list)
    features: dict[str, Any] = field(default_factory=dict)
    raw_data: dict[str, Any] = field(default_factory=dict)
    external_id: str | None = None
    first_listed_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None


class SourceAdapter(ABC):
    """
    Abstract base class for source adapters.

    Each concrete adapter implements fetching from a specific source
    (web scraper, RSS parser, CSV importer) and normalizing the results
    into the common NormalizedProperty schema.
    """

    @abstractmethod
    async def fetch_listings(self, source_config: dict[str, Any]) -> list[RawListing]:
        """
        Fetch raw listing data from the source.

        Args:
            source_config: Adapter-specific configuration dict from the Source model.

        Returns:
            List of raw listings to be parsed.
        """
        ...

    @abstractmethod
    def parse_listing(self, raw: RawListing) -> NormalizedProperty | None:
        """
        Parse a raw listing into a normalized property.

        Returns None if the listing cannot be parsed (invalid data, etc.).

        Args:
            raw: Raw data from fetch_listings.

        Returns:
            Normalized property data ready for storage, or None.
        """
        ...

    @abstractmethod
    def get_adapter_name(self) -> str:
        """Return the unique identifier for this adapter (e.g., 'daft', 'myhome')."""
        ...

    @abstractmethod
    def get_adapter_type(self) -> AdapterType:
        """Return the adapter category (scraper, rss, csv)."""
        ...

    def get_description(self) -> str:
        """Human-readable description of the adapter."""
        return f"{self.get_adapter_name()} adapter"

    def supports_incremental(self) -> bool:
        """Whether this adapter can fetch only new/changed listings since last poll."""
        return False

    def get_default_config(self) -> dict[str, Any]:
        """Return the default configuration dict for this adapter."""
        return {}

    def get_config_schema(self) -> dict[str, Any]:
        """
        Return a JSON-schema-like dict describing the adapter's config options.

        Used by the frontend to render adapter-specific configuration forms.
        """
        return {}

    def validate_config(self, source_config: dict[str, Any]) -> list[str]:
        """Validate config values against ``get_config_schema``.

        Adapters can override for richer validation, but this default catches
        common type mismatches at API boundaries.
        """
        if not isinstance(source_config, dict):
            return ["config must be an object"]

        errors: list[str] = []
        schema = self.get_config_schema() or {}
        for key, rules in schema.items():
            if key not in source_config:
                continue
            value = source_config.get(key)
            expected_type = (rules or {}).get("type")
            if not expected_type:
                continue

            if not _matches_type(value, expected_type):
                errors.append(
                    f"config.{key} must be type '{expected_type}', got '{type(value).__name__}'"
                )
                continue

            if expected_type == "array":
                item_type = ((rules or {}).get("items") or {}).get("type")
                if item_type:
                    for idx, item in enumerate(value):
                        if not _matches_type(item, item_type):
                            errors.append(
                                f"config.{key}[{idx}] must be type '{item_type}', got '{type(item).__name__}'"
                            )
        return errors


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True
