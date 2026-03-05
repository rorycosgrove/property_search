"""
Generic RSS/Atom feed adapter.

Parses RSS and Atom feeds for property-related news articles.
Can be used for Irish Times Property, TheJournal, RTE, etc.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import feedparser

from packages.shared.logging import get_logger
from packages.shared.schemas import AdapterType
from packages.sources.base import NormalizedProperty, RawListing, SourceAdapter

logger = get_logger(__name__)


class RSSAdapter(SourceAdapter):
    """Generic RSS/Atom feed adapter for property news and alerts."""

    def get_adapter_name(self) -> str:
        return "rss"

    def get_adapter_type(self) -> AdapterType:
        return AdapterType.RSS

    def get_description(self) -> str:
        return "Generic RSS/Atom feed adapter — for property news and alerts"

    def supports_incremental(self) -> bool:
        return True  # feedparser handles ETag/Last-Modified

    def get_default_config(self) -> dict[str, Any]:
        return {
            "max_entries": 50,
            "keywords": [],  # Optional keyword filter
        }

    def get_config_schema(self) -> dict[str, Any]:
        return {
            "max_entries": {"type": "integer", "default": 50, "description": "Max entries to process per poll"},
            "keywords": {"type": "array", "items": {"type": "string"}, "description": "Only include entries matching these keywords"},
        }

    async def fetch_listings(self, source_config: dict[str, Any]) -> list[RawListing]:
        """Parse RSS/Atom feed and return entries as RawListings."""
        config = {**self.get_default_config(), **source_config}
        feed_url = config.get("feed_url", config.get("url", ""))
        max_entries = config.get("max_entries", 50)
        keywords = [kw.lower() for kw in config.get("keywords", [])]

        if not feed_url:
            logger.error("rss_no_url", config=config)
            return []

        logger.info("rss_fetch_start", url=feed_url)

        try:
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                logger.warning("rss_parse_error", url=feed_url, error=str(feed.bozo_exception))
                return []

            listings: list[RawListing] = []
            now = datetime.now(timezone.utc)

            for entry in feed.entries[:max_entries]:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))

                # Optional keyword filtering
                if keywords:
                    text = f"{title} {summary}".lower()
                    if not any(kw in text for kw in keywords):
                        continue

                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    except (TypeError, ValueError):
                        pass

                listings.append(
                    RawListing(
                        raw_data={
                            "title": title,
                            "description": summary,
                            "url": entry.get("link", ""),
                            "published_at": published.isoformat() if published else None,
                            "author": entry.get("author", ""),
                            "tags": [tag.get("term", "") for tag in entry.get("tags", [])],
                            "rss_entry": True,
                        },
                        source_url=feed_url,
                        fetched_at=now,
                    )
                )

            logger.info("rss_fetch_complete", url=feed_url, entries=len(listings))
            return listings

        except Exception as e:
            logger.error("rss_fetch_error", url=feed_url, error=str(e))
            return []

    def parse_listing(self, raw: RawListing) -> NormalizedProperty | None:
        """
        Parse an RSS entry.

        RSS entries map loosely to properties — they are news articles,
        not property listings. Stored with minimal property fields.
        """
        data = raw.raw_data
        if not data:
            return None

        return NormalizedProperty(
            title=data.get("title", "").strip(),
            description=data.get("description", ""),
            url=data.get("url", ""),
            address="",  # RSS entries don't have addresses
            raw_data=data,
        )
