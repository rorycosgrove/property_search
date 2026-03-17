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
    # ── Derelict / vacant property grants ────────────────────────────────────
    {
        "code": "IE-DERELICT-CROICONAI-2026",
        "name": "Croí Cónaithe (Towns) Fund",
        "country": "IE",
        "authority": "Department of Housing, Local Government and Heritage",
        "description": (
            "Grants of up to €50,000 for refurbishment of vacant or derelict properties "
            "in towns and villages for use as a principal private residence. "
            "Properties must have been vacant for two or more years."
        ),
        "eligibility_rules": {
            "country": "IE",
            "property_condition": ["vacant", "derelict"],
            "min_vacant_years": 2,
            "occupancy": "principal_private_residence",
        },
        "benefit_type": "grant",
        "max_amount": 50000,
        "currency": "EUR",
        "active": True,
        "source_url": "https://www.gov.ie/en/service/croí-cónaithe-towns-fund/",
    },
    {
        "code": "IE-DERELICT-VACANT-REFURB-2026",
        "name": "Vacant Property Refurbishment Grant",
        "country": "IE",
        "authority": "Department of Housing, Local Government and Heritage",
        "description": (
            "Grants of up to €50,000 (vacant) or €70,000 (derelict) for bringing "
            "a long-vacant or derelict property back into use as a home. "
            "Only available for properties vacant for two years or more."
        ),
        "eligibility_rules": {
            "country": "IE",
            "property_condition": ["vacant", "derelict"],
            "min_vacant_years": 2,
        },
        "benefit_type": "grant",
        "max_amount": 70000,
        "currency": "EUR",
        "active": True,
        "source_url": "https://www.gov.ie/en/service/vacant-property-refurbishment-grant/",
    },
    {
        "code": "IE-DERELICT-POBAL-TOWN-2026",
        "name": "Town and Village Renewal Scheme (Derelict Buildings)",
        "country": "IE",
        "authority": "Department of Rural and Community Development / Pobal",
        "description": (
            "Capital funding for renovation and repurposing of derelict or vacant "
            "buildings in rural towns and villages. Administered by Pobal on behalf of "
            "the Department of Rural and Community Development."
        ),
        "eligibility_rules": {
            "country": "IE",
            "property_condition": ["derelict", "vacant"],
            "location_type": "rural_town",
        },
        "benefit_type": "grant",
        "max_amount": 200000,
        "currency": "EUR",
        "active": True,
        "source_url": "https://www.gov.ie/en/service/town-and-village-renewal-scheme/",
    },
    {
        "code": "IE-DERELICT-COMPULSORY-CPO-2026",
        "name": "Derelict Sites Act – CPO / Local Authority Acquisition",
        "country": "IE",
        "authority": "Local Authorities (Ireland)",
        "description": (
            "Local authorities have powers under the Derelict Sites Act 1990 to compulsorily "
            "acquire derelict land and buildings. Properties on the Derelict Sites Register "
            "are subject to an annual 3% levy on market value and may be acquired by CPO."
        ),
        "eligibility_rules": {
            "country": "IE",
            "property_condition": ["derelict"],
            "note": "This is a statutory mechanism, not a buyer grant. Included for information.",
        },
        "benefit_type": "statutory_mechanism",
        "active": True,
        "source_url": "https://www.gov.ie/en/collection/derelict-sites/",
    },
    {
        "code": "IE-DERELICT-COMPACTGROWTH-2026",
        "name": "Compact Growth / Urban Regeneration Fund (URDF)",
        "country": "IE",
        "authority": "Department of Housing, Local Government and Heritage",
        "description": (
            "Urban Regeneration and Development Fund (URDF) supports regeneration projects "
            "including derelict and vacant land in cities and large towns. Delivered via local "
            "authorities and approved housing bodies."
        ),
        "eligibility_rules": {
            "country": "IE",
            "property_condition": ["derelict", "vacant"],
            "location_type": "urban",
            "applicant_type": "local_authority_or_ahb",
        },
        "benefit_type": "capital_grant",
        "max_amount": 5000000,
        "currency": "EUR",
        "active": True,
        "source_url": "https://www.gov.ie/en/collection/urban-regeneration-development-fund/",
    },
    {
        "code": "NI-DERELICT-NIHE-REPAIR-2026",
        "name": "NIHE Repair Grant – Unfit Dwelling (NI)",
        "country": "NI",
        "authority": "Northern Ireland Housing Executive (NIHE)",
        "description": (
            "Mandatory grants for bringing unfit dwellings up to standard in Northern Ireland. "
            "Means-tested grants available for owner-occupiers and private landlords to repair "
            "properties that are currently unfit for habitation."
        ),
        "eligibility_rules": {
            "country": "NI",
            "property_condition": ["derelict", "unfit"],
            "occupancy": "owner_occupier_or_private_landlord",
        },
        "benefit_type": "grant",
        "max_amount": 30000,
        "currency": "GBP",
        "active": True,
        "source_url": "https://www.nihe.gov.uk/housing-help/grants-and-adaptations",
    },
    {
        "code": "NI-DERELICT-DFC-REGEN-2026",
        "name": "DfC Derelict Land / Urban Regeneration Grant (NI)",
        "country": "NI",
        "authority": "Department for Communities (Northern Ireland)",
        "description": (
            "Funding through the Urban Regeneration programme for bringing derelict land "
            "and buildings back into productive use in Northern Ireland town and city centres."
        ),
        "eligibility_rules": {
            "country": "NI",
            "property_condition": ["derelict"],
            "location_type": "urban",
        },
        "benefit_type": "capital_grant",
        "active": True,
        "source_url": "https://www.communities-ni.gov.uk/topics/urban-regeneration",
    },
    # ── Energy retrofit (extends existing SEAI with BER focus) ───────────────
    {
        "code": "IE-SEAI-DEEP-RETROFIT-2026",
        "name": "SEAI Deep Retrofit Grant",
        "country": "IE",
        "authority": "Sustainable Energy Authority of Ireland",
        "description": (
            "Grants for comprehensive deep energy retrofits targeting a minimum B2 BER rating. "
            "Available for homes built before 2011. Particularly relevant for older derelict "
            "properties being brought back into use."
        ),
        "eligibility_rules": {
            "country": "IE",
            "max_construction_year": 2011,
            "target_ber": "B2",
        },
        "benefit_type": "grant",
        "max_amount": 50000,
        "currency": "EUR",
        "active": True,
        "source_url": "https://www.seai.ie/grants/home-energy-grants/deep-retrofit-grant/",
    },
    # ── First-time buyer / affordability ──────────────────────────────────────
    {
        "code": "IE-AFFORDABLEHOUSING-LDA-2026",
        "name": "Land Development Agency Affordable Purchase Scheme",
        "country": "IE",
        "authority": "Land Development Agency (LDA)",
        "description": (
            "Affordable homes developed by the LDA on State and public land, sold below "
            "open-market prices to eligible first-time buyers. Properties subject to a "
            "clawback on resale for a set period."
        ),
        "eligibility_rules": {
            "country": "IE",
            "buyer_type": ["first_time_buyer"],
        },
        "benefit_type": "affordable_price",
        "active": True,
        "source_url": "https://www.lda.ie/homes/",
    },
    {
        "code": "IE-LOCALAUTHORITY-HOMEBUY-2026",
        "name": "Local Authority Affordable Purchase Scheme",
        "country": "IE",
        "authority": "Local Authorities (Ireland)",
        "description": (
            "Equity-share scheme allowing first-time buyers to purchase local authority "
            "developed homes at a reduced price in exchange for the authority retaining an "
            "equity stake. Managed by individual councils."
        ),
        "eligibility_rules": {
            "country": "IE",
            "buyer_type": ["first_time_buyer"],
        },
        "benefit_type": "equity_share",
        "active": True,
        "source_url": "https://www.gov.ie/en/service/local-authority-affordable-purchase-scheme/",
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
