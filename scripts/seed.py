"""Seed default data sources and grants into the database."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from packages.storage.database import get_session
from packages.storage.models import GrantProgram, Source
from packages.shared.config import get_settings


DEFAULT_SOURCES = [
    {
        "name": "Daft.ie – National",
        "url": "https://www.daft.ie/property-for-sale/ireland",
        "adapter_type": "api",
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


DEFAULT_GRANTS = [
    {
        "code": "IE-SEAI-HOME-ENERGY-2026",
        "name": "SEAI Home Energy Upgrade Grants",
        "country": "IE",
        "authority": "Sustainable Energy Authority of Ireland",
        "description": "Supports insulation, heat pumps, and energy retrofit measures.",
        "eligibility_rules": {"country": "IE", "max_ber": "D2"},
        "benefit_type": "rebate",
        "max_amount": 8000,
        "currency": "EUR",
        "active": True,
        "source_url": "https://www.seai.ie/grants/home-energy-grants/",
    },
    {
        "code": "IE-HTB-2026",
        "name": "Help to Buy (HTB)",
        "country": "IE",
        "authority": "Revenue Commissioners",
        "description": "Tax refund support for first-time buyers purchasing or self-building a new home.",
        "eligibility_rules": {"country": "IE", "property_types": ["house", "apartment"], "max_price": 500000},
        "benefit_type": "tax_refund",
        "max_amount": 30000,
        "currency": "EUR",
        "active": True,
        "source_url": "https://www.revenue.ie/en/property/help-to-buy-incentive/index.aspx",
    },
    {
        "code": "IE-FIRST-HOME-SCHEME-2026",
        "name": "First Home Scheme",
        "country": "IE",
        "authority": "First Home Scheme DAC",
        "description": "Shared equity support for eligible first-time buyers in Ireland.",
        "eligibility_rules": {"country": "IE", "property_types": ["house", "apartment"]},
        "benefit_type": "equity_support",
        "max_amount": 75000,
        "currency": "EUR",
        "active": True,
        "source_url": "https://www.firsthomescheme.ie/",
    },
    {
        "code": "NI-COOWN-2026",
        "name": "Co-Ownership Scheme (NI)",
        "country": "NI",
        "authority": "Co-Ownership Housing",
        "description": "Shared ownership support for eligible buyers in Northern Ireland.",
        "eligibility_rules": {"country": "NI", "counties": ["antrim", "armagh", "down", "fermanagh", "derry", "londonderry", "tyrone"]},
        "benefit_type": "shared_ownership",
        "currency": "GBP",
        "active": True,
        "source_url": "https://www.co-ownership.org/",
    },
]


def seed_sources() -> None:
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


def seed_grants() -> None:
    with get_session() as session:
        existing = {g.code for g in session.query(GrantProgram).all()}
        added = 0
        for grant_data in DEFAULT_GRANTS:
            if grant_data["code"] in existing:
                print(f"  [skip] {grant_data['code']} already exists")
                continue
            grant = GrantProgram(**grant_data)
            session.add(grant)
            added += 1
            print(f"  [add]  {grant_data['code']}")
        session.commit()
        print(f"\nSeeded {added} new grant program(s). ({len(existing)} already existed)")


def seed_all() -> None:
    _ = get_settings()
    print("Seeding default sources...")
    seed_sources()
    print("\nSeeding default grant programs...")
    seed_grants()


if __name__ == "__main__":
    seed_all()
