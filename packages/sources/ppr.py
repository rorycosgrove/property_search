"""
Property Price Register (PPR) CSV adapter.

Downloads and parses the PPR-ALL.zip file from propertypriceregister.ie.
Contains all residential property sales in Ireland since January 2010.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from typing import Any

import httpx
import pandas as pd

from packages.shared.config import settings
from packages.shared.logging import get_logger
from packages.shared.schemas import AdapterType
from packages.shared.utils import extract_county
from packages.sources.base import NormalizedProperty, RawListing, SourceAdapter

logger = get_logger(__name__)

PPR_DOWNLOAD_URL = (
    "https://www.propertypriceregister.ie/website/npsra/ppr/npsra-ppr.nsf"
    "/Downloads/PPR-ALL.zip/$FILE/PPR-ALL.zip"
)


class PPRAdapter(SourceAdapter):
    """
    Adapter for the Property Price Register (PPR).

    Downloads the full CSV of all residential property sales since 2010.
    Designed to run weekly. Produces SoldProperty records, not Property listings.
    """

    def get_adapter_name(self) -> str:
        return "ppr"

    def get_adapter_type(self) -> AdapterType:
        return AdapterType.CSV

    def get_description(self) -> str:
        return "Property Price Register — all Irish residential sales since 2010"

    def supports_incremental(self) -> bool:
        return True  # Can track last import date

    def get_default_config(self) -> dict[str, Any]:
        return {
            "download_url": PPR_DOWNLOAD_URL,
            "min_year": None,  # If set, only import from this year onward
        }

    def get_config_schema(self) -> dict[str, Any]:
        return {
            "download_url": {"type": "string", "description": "URL to download PPR-ALL.zip"},
            "min_year": {"type": "integer", "description": "Only import sales from this year onward"},
        }

    async def fetch_listings(self, source_config: dict[str, Any]) -> list[RawListing]:
        """
        Download and parse PPR CSV.

        Returns RawListings containing row data (not HTML).
        """
        config = {**self.get_default_config(), **source_config}
        url = config.get("download_url", PPR_DOWNLOAD_URL)
        min_year = config.get("min_year")

        logger.info("ppr_download_start", url=url)

        try:
            async with httpx.AsyncClient(
                timeout=120,  # Large file, longer timeout
                headers={"User-Agent": settings.user_agent},
                follow_redirects=True,
                verify=False,  # PPR cert chain is sometimes incomplete
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            # Extract CSV from zip
            zip_buffer = io.BytesIO(response.content)
            with zipfile.ZipFile(zip_buffer) as zf:
                csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
                if not csv_names:
                    logger.error("ppr_no_csv_in_zip")
                    return []

                with zf.open(csv_names[0]) as csv_file:
                    # PPR CSV uses Latin-1 encoding
                    df = pd.read_csv(
                        csv_file,
                        encoding="latin-1",
                        low_memory=False,
                        dtype={
                            "Property Size Description": "string",
                            "Cur Síos ar Mhéid na Maoine": "string",
                        },
                    )

            logger.info("ppr_csv_loaded", rows=len(df))

            # Standardize column names
            df.columns = [c.strip() for c in df.columns]

            # Filter by year if configured
            if min_year:
                df = self._filter_by_year(df, min_year)

            # Convert to RawListings
            listings = []
            now = datetime.now(UTC)
            for _, row in df.iterrows():
                listings.append(
                    RawListing(
                        raw_data=row.to_dict(),
                        source_url=url,
                        fetched_at=now,
                    )
                )

            logger.info("ppr_fetch_complete", total_records=len(listings))
            return listings

        except Exception as e:
            logger.error("ppr_download_error", error=str(e))
            return []

    def parse_listing(self, raw: RawListing) -> NormalizedProperty | None:
        """
        Parse a PPR CSV row into data suitable for the SoldProperty table.

        Note: PPR data maps to SoldProperty, not Property. The worker task
        handles this distinction. We still return NormalizedProperty for
        interface consistency, with sold-specific fields in raw_data.
        """
        data = raw.raw_data
        if not data:
            return None

        try:
            # PPR columns (may vary by language; handle both Irish and English)
            address = str(data.get("Address", data.get("Seoladh", ""))).strip()
            county = str(data.get("County", data.get("Contae", ""))).strip()
            price_str = str(data.get("Price (€)", data.get("Praghas (€)", ""))).strip()
            date_str = str(data.get("Date of Sale (dd/mm/yyyy)", data.get("Dáta Díolta (dd/mm/yyyy)", ""))).strip()
            not_full_market = str(data.get("Not Full Market Price", data.get("Ní Praghas Iomlán an Mhargaidh", ""))).strip()
            vat_exclusive = str(data.get("VAT Exclusive", data.get("Gan CBL", ""))).strip()
            description = str(data.get("Description of Property", data.get("Cur Síos ar an Maoin", ""))).strip()
            size_desc = str(data.get("Property Size Description", data.get("Cur Síos ar Mhéid na Maoine", ""))).strip()

            # Parse price: "€350,000.00" or "350,000"
            price_cleaned = price_str.replace("€", "").replace(",", "").strip()
            try:
                price = float(price_cleaned) if price_cleaned else None
            except ValueError:
                price = None

            # Standardize county name
            county_std = extract_county(f"{address}, {county}") or county

            # Content hash for dedup
            content_hash = hashlib.sha256(
                f"{address}|{date_str}|{price_str}".encode()
            ).hexdigest()

            return NormalizedProperty(
                title=address,
                address=address,
                county=county_std,
                price=price,
                price_text=price_str,
                raw_data={
                    "sale_date": date_str,
                    "is_new": "new" in description.lower(),
                    "is_full_market_price": not_full_market.lower() not in ("yes", "tá"),
                    "vat_exclusive": vat_exclusive.lower() in ("yes", "tá"),
                    "property_size_description": size_desc if size_desc and size_desc != "nan" else None,
                    "content_hash": content_hash,
                    "ppr_record": True,  # Flag for worker to route to SoldProperty table
                },
                url="https://www.propertypriceregister.ie",
            )
        except Exception as e:
            logger.debug("ppr_parse_error", error=str(e))
            return None

    @staticmethod
    def _filter_by_year(df: pd.DataFrame, min_year: int) -> pd.DataFrame:
        """Filter PPR dataframe to only include records from min_year onward."""
        date_col = None
        for col in df.columns:
            if "date" in col.lower() or "dáta" in col.lower():
                date_col = col
                break

        if date_col:
            try:
                df[date_col] = pd.to_datetime(df[date_col], format="%d/%m/%Y", errors="coerce")
                df = df[df[date_col].dt.year >= min_year]
            except Exception:
                pass
        else:
            logger.warning("ppr_date_column_not_found", min_year=min_year, columns=list(df.columns))

        return df
