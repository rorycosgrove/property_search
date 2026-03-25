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
3. SQS worker Lambda calls adapters through the pipeline: `fetch → parse → normalize → geocode → store`
4. Deduplication happens via `content_hash` (SHA-256 of the source URL)

## Execution Model

Adapters are invoked by Lambda workers consuming from the **scrape** SQS queue:

```
EventBridge (every 6h)
  → scrape_all_sources() sends N messages to SQS scrape queue
    → Lambda worker: scrape_source(source_id)
      → registry.get_adapter(adapter_name)(config)
      → adapter.fetch_listings()
      → adapter.parse_listing() per listing
      → normalizer.normalize()
      → geocoder.geocode()
      → repository.upsert()
```

## Writing a Custom Adapter

### Step 1: Create the adapter file

```python
# packages/sources/my_source.py
from packages.sources.base import SourceAdapter, RawListing, NormalizedProperty
import httpx


class MySourceAdapter(SourceAdapter):
    """Adapter for mysource.com."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def get_adapter_name(self) -> str:
        return "mysource"

    def get_adapter_type(self) -> str:
        return "scraper"

    async def fetch_listings(self, source_config: dict) -> list[RawListing]:
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
                    raw_data=item,
                ))

        return listings

    def parse_listing(self, raw: RawListing) -> NormalizedProperty | None:
        """Convert a raw listing to a normalized property."""
        data = raw.raw_data
        return NormalizedProperty(
            title=data.get("title", ""),
            url=raw.source_url,
            address=data.get("address", ""),
            price=data.get("price"),
            bedrooms=data.get("beds"),
            bathrooms=data.get("baths"),
            property_type=data.get("type", "house"),
            description=data.get("description"),
            images=[{"url": url} for url in data.get("images", [])],
            raw_data=data,
            external_id=str(data.get("id")) if data.get("id") is not None else None,
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
curl -X POST https://<api-url>/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MySource – Dublin",
        "url": "https://mysource.com/dublin",
        "adapter_type": "scraper",
    "adapter_name": "mysource",
        "poll_interval_seconds": 900,
        "tags": [],
    "enabled": true,
    "config": {"region": "dublin"}
  }'
```

Or via seed script — add to `DEFAULT_SOURCES` in `scripts/seed.py`.

### Step 4: Test

```bash
# Trigger a manual scrape via API
curl -X POST https://<api-url>/api/v1/sources/{source_id}/trigger
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
        """Return adapter type: 'scraper', 'csv', 'rss', etc."""

    @classmethod
    def get_default_config(cls) -> dict:
        """Default configuration for this adapter."""

    @classmethod
    def get_config_schema(cls) -> dict:
        """JSON schema describing adapter configuration options."""
```

## Rate Limiting

All HTTP-based adapters use `httpx.AsyncClient` with timeouts. The scraping pipeline includes:
- Per-adapter timeout (configurable)
- Nominatim geocoding rate limit (1 req/sec per OSM policy)
- SQS visibility timeout ensures long-running scrapes don't get retried prematurely

## Source Contract Notes

- A source record requires `name`, `url`, `adapter_type`, and `adapter_name`.
- The backend canonicalizes `url` and rejects duplicates by canonical source identity.
- Discovery-created sources are usually inserted disabled and tagged `pending_approval` until explicitly approved.
