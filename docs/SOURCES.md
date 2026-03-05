# Source Adapter System

The property search platform uses a pluggable adapter system to fetch listings from different websites and data sources. Each adapter implements a common interface, making it easy to add new sources without modifying the core scraping pipeline.

## Built-in Adapters

| Adapter | Key | Type | Description |
|---------|-----|------|-------------|
| Daft.ie | `daft` | scraper | Ireland's largest property portal |
| MyHome.ie | `myhome` | scraper | Irish Times property listings |
| PropertyPal | `propertypal` | scraper | Popular in ROI + Northern Ireland |
| PPR | `ppr` | csv | Property Price Register (sold prices) |
| RSS | `rss` | rss | Generic RSS/Atom feed adapter |

## How It Works

1. Each adapter extends the `SourceAdapter` abstract base class
2. Adapters are registered in `packages/sources/registry.py`
3. The Celery worker calls adapters through the pipeline: `fetch → parse → normalize → geocode → store`
4. Deduplication happens via `content_hash` (SHA-256 of the source URL)

## Writing a Custom Adapter

### Step 1: Create the adapter file

```python
# packages/sources/my_source.py
from packages.sources.base import SourceAdapter, RawListing, NormalizedProperty
from packages.shared.config import get_settings
import httpx


class MySourceAdapter(SourceAdapter):
    """Adapter for mysource.com."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.settings = get_settings()

    def get_adapter_name(self) -> str:
        return "mysource"

    def get_adapter_type(self) -> str:
        return "scraper"

    async def fetch_listings(self) -> list[RawListing]:
        """Fetch raw listings from the source."""
        listings = []
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://mysource.com/api/listings",
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data["listings"]:
                listings.append(RawListing(
                    source_url=f"https://mysource.com/listing/{item['id']}",
                    title=item["title"],
                    price=str(item["price"]),
                    address=item["address"],
                    raw_data=item,  # Store everything for parse_listing
                ))

        return listings

    def parse_listing(self, raw: RawListing) -> NormalizedProperty | None:
        """Convert a raw listing to a normalized property."""
        data = raw.raw_data
        return NormalizedProperty(
            source_url=raw.source_url,
            title=raw.title,
            address=raw.address,
            price=data.get("price"),
            bedrooms=data.get("beds"),
            bathrooms=data.get("baths"),
            property_type=data.get("type", "house"),
            description=data.get("description"),
            image_urls=data.get("images", []),
        )

    @classmethod
    def get_default_config(cls) -> dict:
        return {"region": "dublin"}

    @classmethod
    def get_config_schema(cls) -> dict:
        return {
            "region": {"type": "string", "description": "Region to search"},
        }
```

### Step 2: Register the adapter

```python
# In packages/sources/registry.py, add to BUILTIN_ADAPTERS:
from packages.sources.my_source import MySourceAdapter

BUILTIN_ADAPTERS = {
    # ... existing adapters ...
    "mysource": {
        "class": MySourceAdapter,
        "description": "MySource.com property listings",
        "adapter_type": "scraper",
    },
}
```

### Step 3: Create a source record

Via API:
```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MySource – Dublin",
    "adapter_name": "mysource",
    "enabled": true,
    "config": {"region": "dublin"}
  }'
```

Or via seed script — add to `DEFAULT_SOURCES` in `scripts/seed.py`.

### Step 4: Test

```bash
# Trigger a manual scrape
curl -X POST http://localhost:8000/api/v1/sources/{source_id}/trigger
```

## Adapter Interface

```python
class SourceAdapter(ABC):
    @abstractmethod
    async def fetch_listings(self) -> list[RawListing]:
        """Fetch raw listing data from the source."""

    @abstractmethod
    def parse_listing(self, raw: RawListing) -> NormalizedProperty | None:
        """Parse a raw listing into a normalized property."""

    @abstractmethod
    def get_adapter_name(self) -> str:
        """Return the unique adapter key."""

    @abstractmethod
    def get_adapter_type(self) -> str:
        """Return the adapter type (scraper, api, csv, rss)."""

    def supports_incremental(self) -> bool:
        """Whether adapter supports incremental fetching (default: False)."""
        return False
```

## Data Classes

```python
@dataclass
class RawListing:
    source_url: str        # Unique URL (used for content_hash)
    title: str
    price: str | None
    address: str
    raw_data: dict         # All scraped fields for parse_listing

@dataclass
class NormalizedProperty:
    source_url: str
    title: str
    address: str
    county: str | None
    eircode: str | None
    price: float | None
    bedrooms: int | None
    bathrooms: int | None
    floor_area_sqm: float | None
    property_type: str | None
    ber_rating: str | None
    description: str | None
    image_urls: list[str]
    latitude: float | None
    longitude: float | None
    content_hash: str       # Auto-computed from source_url
    fuzzy_hash: str | None  # Auto-computed from address + price
    raw_data: dict
```

## Configuration

Each adapter can define its own config schema. Config is stored as JSONB on the `source` record and passed to the adapter constructor.

## Rate Limiting

Adapters should implement their own rate limiting. The built-in scrapers use:
- 1-3 second delays between page requests
- Respect for `robots.txt` (informational — no enforcement)
- User-Agent header identifying the bot

## Error Handling

- If `fetch_listings()` raises an exception, the worker records the error on the source record
- `consecutive_errors` is incremented; resets on success
- After 10 consecutive errors, the source is automatically disabled
- Individual `parse_listing()` failures are logged but don't stop the batch
