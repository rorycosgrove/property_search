"""Seed default data sources into the database."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from packages.storage.database import get_session
from packages.storage.models import Source
from packages.shared.config import get_settings


DEFAULT_SOURCES = [
    {
        "name": "Daft.ie – National",
        "url": "https://www.daft.ie/property-for-sale/ireland",
        "adapter_type": "scraper",
        "adapter_name": "daft",
        "enabled": True,
        "config": {"county": None, "sale_type": "sale"},
    },
    {
        "name": "MyHome.ie – National",
        "url": "https://www.myhome.ie/residential/ireland/property-for-sale",
        "adapter_type": "scraper",
        "adapter_name": "myhome",
        "enabled": True,
        "config": {"county": None},
    },
    {
        "name": "PropertyPal – ROI",
        "url": "https://www.propertypal.com/property-for-sale/republic-of-ireland",
        "adapter_type": "scraper",
        "adapter_name": "propertypal",
        "enabled": True,
        "config": {"region": "republic-of-ireland"},
    },
    {
        "name": "PropertyPal – Northern Ireland",
        "url": "https://www.propertypal.com/property-for-sale/northern-ireland",
        "adapter_type": "scraper",
        "adapter_name": "propertypal",
        "enabled": True,
        "config": {"region": "northern-ireland"},
    },
    {
        "name": "Property Price Register",
        "url": "https://www.propertypriceregister.ie",
        "adapter_type": "csv",
        "adapter_name": "ppr",
        "enabled": True,
        "config": {"years": 2},
    },
]


def seed_sources() -> None:
    settings = get_settings()
    with get_session() as session:
        existing = {s.name for s in session.query(Source).all()}
        added = 0
        for src_data in DEFAULT_SOURCES:
            if src_data["name"] in existing:
                print(f"  [skip] {src_data['name']} already exists")
                continue
            source = Source(**src_data)
            session.add(source)
            added += 1
            print(f"  [add]  {src_data['name']}")
        session.commit()
        print(f"\nSeeded {added} new source(s). ({len(existing)} already existed)")


if __name__ == "__main__":
    seed_sources()
