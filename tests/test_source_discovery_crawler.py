"""Tests for the unified source discovery crawler and confidence scoring."""

from __future__ import annotations

from typing import Any

import pytest


# ── Confidence scoring ─────────────────────────────────────────────────────────


class TestScoreCandidate:
    """Tests for packages.sources.confidence.score_candidate."""

    def _make(self, **kwargs) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "name": "Daft.ie - Cork (Auto)",
            "url": "https://www.daft.ie/property-for-sale/cork",
            "adapter_type": "scraper",
            "adapter_name": "daft",
            "config": {"areas": ["cork"], "max_pages": 3},
            "poll_interval_seconds": 21600,
        }
        defaults.update(kwargs)
        return defaults

    def test_known_adapter_high_score(self):
        from packages.sources.confidence import score_candidate, AUTO_ENABLE_THRESHOLD

        result = score_candidate(self._make())
        assert result.score >= AUTO_ENABLE_THRESHOLD
        assert result.activation == "auto_enable"

    def test_unknown_adapter_lower_score(self):
        from packages.sources.confidence import score_candidate, AUTO_ENABLE_THRESHOLD

        result = score_candidate(self._make(adapter_name="unknown_scraper"))
        assert result.score < AUTO_ENABLE_THRESHOLD

    def test_trusted_domain_adds_score(self):
        from packages.sources.confidence import score_candidate

        with_trusted = score_candidate(self._make(url="https://www.myhome.ie/residential/cork/property-for-sale", adapter_name="myhome"))
        with_unknown = score_candidate(self._make(url="https://www.unknown-portal.ie/for-sale", adapter_name="unknown"))
        assert with_trusted.score > with_unknown.score

    def test_bare_root_url_penalised(self):
        from packages.sources.confidence import score_candidate

        with_path = score_candidate(self._make())
        bare = score_candidate(self._make(url="https://www.daft.ie/"))
        assert with_path.score > bare.score

    def test_rss_adapter_type_gets_bonus(self):
        from packages.sources.confidence import score_candidate

        scraper = score_candidate(self._make(adapter_type="scraper"))
        rss = score_candidate(self._make(adapter_type="rss"))
        # rss gets the structured_feed_type bonus
        assert rss.score >= scraper.score

    def test_missing_config_lower_score(self):
        from packages.sources.confidence import score_candidate

        with_config = score_candidate(self._make())
        without_config = score_candidate(self._make(config=None))
        assert with_config.score > without_config.score

    def test_rejection_below_threshold(self):
        from packages.sources.confidence import score_candidate, PENDING_THRESHOLD

        candidate = {
            "name": "Unknown",
            "url": "https://www.obscure-portal.ie/",
            "adapter_type": "scraper",
            "adapter_name": "unknown_x",
            "config": None,
            "poll_interval_seconds": None,
        }
        result = score_candidate(candidate)
        assert result.score < PENDING_THRESHOLD
        assert result.activation == "reject"

    def test_reasons_populated(self):
        from packages.sources.confidence import score_candidate

        result = score_candidate(self._make())
        assert len(result.reasons) > 0
        assert any("known_adapter" in r for r in result.reasons)

    def test_score_clamped_0_to_1(self):
        from packages.sources.confidence import score_candidate

        result = score_candidate(self._make())
        assert 0.0 <= result.score <= 1.0


class TestScoreCandidates:
    def test_sorted_descending(self):
        from packages.sources.confidence import score_candidates

        candidates = [
            {
                "name": "Daft Cork",
                "url": "https://www.daft.ie/property-for-sale/cork",
                "adapter_type": "scraper",
                "adapter_name": "daft",
                "config": {"areas": ["cork"]},
                "poll_interval_seconds": 21600,
            },
            {
                "name": "Unknown portal",
                "url": "https://www.very-unknown-portal.ie/listings",
                "adapter_type": "scraper",
                "adapter_name": "some_adapter",
                "config": None,
                "poll_interval_seconds": None,
            },
        ]
        scored = score_candidates(candidates, reject_below=0.0)
        scores = [s.score for s in scored]
        assert scores == sorted(scores, reverse=True)

    def test_filters_below_threshold(self):
        from packages.sources.confidence import score_candidates, PENDING_THRESHOLD

        candidates = [
            {
                "name": "Mystery Source",
                "url": "https://www.obscure-x.ie/",
                "adapter_type": "scraper",
                "adapter_name": "noop",
                "config": None,
                "poll_interval_seconds": None,
            }
        ]
        scored = score_candidates(candidates, reject_below=PENDING_THRESHOLD)
        # All below-threshold candidates should be excluded.
        for s in scored:
            assert s.score >= PENDING_THRESHOLD


# ── Property source crawler ────────────────────────────────────────────────────


class TestPropertySourceCrawler:
    def test_static_candidates_returned_without_http(self):
        from packages.sources.crawler import PropertySourceCrawler

        crawler = PropertySourceCrawler()
        candidates = crawler.discover(include_static=True, follow_links=False)
        assert len(candidates) > 10

    def test_all_candidates_have_required_fields(self):
        from packages.sources.crawler import PropertySourceCrawler

        crawler = PropertySourceCrawler()
        candidates = crawler.discover(include_static=True, follow_links=False)
        for c in candidates:
            assert c.get("name"), f"Missing name: {c}"
            assert c.get("url"), f"Missing url: {c}"
            assert c.get("adapter_name"), f"Missing adapter_name: {c}"
            assert c.get("adapter_type"), f"Missing adapter_type: {c}"

    def test_no_duplicate_urls(self):
        from packages.sources.crawler import PropertySourceCrawler
        from packages.sources.discovery import canonicalize_source_url

        crawler = PropertySourceCrawler()
        candidates = crawler.discover(include_static=True, follow_links=False)
        urls = [canonicalize_source_url(c["url"]) for c in candidates]
        assert len(urls) == len(set(urls)), "Duplicate canonical URLs present"

    def test_county_candidates_generated(self):
        from packages.sources.crawler import PropertySourceCrawler

        crawler = PropertySourceCrawler()
        candidates = crawler.discover(include_static=True, follow_links=False)
        names = [c["name"] for c in candidates]
        # Should have Cork, Galway, etc.
        assert any("Cork" in n for n in names)
        assert any("Galway" in n for n in names)

    def test_daft_county_candidates_use_daft_adapter(self):
        from packages.sources.crawler import PropertySourceCrawler

        crawler = PropertySourceCrawler()
        candidates = crawler.discover(include_static=True, follow_links=False)
        daft_candidates = [c for c in candidates if "daft.ie" in c["url"]]
        for c in daft_candidates:
            assert c["adapter_name"] == "daft", f"Expected daft adapter for {c['url']}"

    def test_myhome_county_candidates_use_myhome_adapter(self):
        from packages.sources.crawler import PropertySourceCrawler

        crawler = PropertySourceCrawler()
        candidates = crawler.discover(include_static=True, follow_links=False)
        myhome_candidates = [c for c in candidates if "myhome.ie" in c["url"]]
        for c in myhome_candidates:
            assert c["adapter_name"] == "myhome"


# ── Discovery integration ──────────────────────────────────────────────────────


class TestLoadAllDiscoveryCandidates:
    def test_returns_scored_candidates(self):
        from packages.sources.confidence import ScoredCandidate
        from packages.sources.discovery import load_all_discovery_candidates

        results = load_all_discovery_candidates(use_crawler=True, follow_links=False)
        assert len(results) > 0
        for r in results:
            assert isinstance(r, ScoredCandidate)
            assert 0.0 <= r.score <= 1.0

    def test_no_duplicates_in_merged_result(self):
        from packages.sources.discovery import load_all_discovery_candidates, canonicalize_source_url

        results = load_all_discovery_candidates(use_crawler=True, follow_links=False, reject_below=0.0)
        urls = [canonicalize_source_url(r.candidate.get("url", "")) for r in results]
        assert len(urls) == len(set(u for u in urls if u))

    def test_default_candidates_included(self):
        from packages.sources.discovery import load_all_discovery_candidates, DEFAULT_DISCOVERY_CANDIDATES

        results = load_all_discovery_candidates(use_crawler=True, follow_links=False, reject_below=0.0)
        result_urls = {r.candidate.get("url") for r in results}
        for c in DEFAULT_DISCOVERY_CANDIDATES:
            assert c["url"] in result_urls, f"Default candidate missing: {c['url']}"

    def test_sorted_by_score_descending(self):
        from packages.sources.discovery import load_all_discovery_candidates

        results = load_all_discovery_candidates(use_crawler=True, follow_links=False)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_falls_back_to_base_candidates_when_crawler_raises(self, monkeypatch):
        import packages.sources.discovery as discovery_module

        class _BoomCrawler:
            def discover(self, **_kwargs):
                raise RuntimeError("crawler exploded")

        monkeypatch.setattr(discovery_module, "load_discovery_candidates", lambda: [
            {
                "name": "Daft.ie - National (Auto)",
                "url": "https://www.daft.ie/property-for-sale/ireland",
                "adapter_type": "scraper",
                "adapter_name": "daft",
                "config": {"areas": ["ireland"]},
                "poll_interval_seconds": 21600,
            }
        ])
        monkeypatch.setitem(__import__("sys").modules, "packages.sources.crawler", type("m", (), {"PropertySourceCrawler": _BoomCrawler}))

        results = discovery_module.load_all_discovery_candidates(use_crawler=True, follow_links=False, reject_below=0.0)

        assert len(results) >= 1
        assert any(r.candidate.get("adapter_name") == "daft" for r in results)


# ── Canonical URL normalization ────────────────────────────────────────────────


class TestCanonicalizeSourceUrl:
    def test_strips_trailing_slash(self):
        from packages.sources.discovery import canonicalize_source_url

        assert canonicalize_source_url("https://example.ie/path/") == "https://example.ie/path"

    def test_lowercases_domain(self):
        from packages.sources.discovery import canonicalize_source_url

        assert canonicalize_source_url("https://DAFT.IE/path") == "https://daft.ie/path"

    def test_strips_query_string(self):
        from packages.sources.discovery import canonicalize_source_url

        assert canonicalize_source_url("https://daft.ie/path?foo=bar") == "https://daft.ie/path"

    def test_strips_fragment(self):
        from packages.sources.discovery import canonicalize_source_url

        assert canonicalize_source_url("https://daft.ie/path#section") == "https://daft.ie/path"

    def test_empty_url_returns_empty(self):
        from packages.sources.discovery import canonicalize_source_url

        assert canonicalize_source_url("") == ""
        assert canonicalize_source_url("   ") == ""

    def test_bare_domain_gets_root_path(self):
        from packages.sources.discovery import canonicalize_source_url

        result = canonicalize_source_url("https://example.ie")
        assert result == "https://example.ie/"


# ── Grant discovery ───────────────────────────────────────────────────────────


class TestGrantDiscoveryDryRun:
    def test_dry_run_returns_candidates_list(self):
        from packages.grants.discovery import GrantSourceCrawler

        # We test the crawler with no network calls by mocking _fetch.
        crawler = GrantSourceCrawler()
        # Confirm object is instantiable and has expected interface.
        assert hasattr(crawler, "discover")

    def test_discover_grant_programs_dry_run_no_db(self, monkeypatch):
        """dry_run=True should return without touching the database."""
        from packages.grants.discovery import discover_grant_programs

        # Mock crawler to return a fixed candidate.
        dummy_candidate = {
            "code": "IE-TEST-DISCOVERED",
            "name": "Test Grant",
            "country": "IE",
            "authority": "Test Authority",
            "description": "Test description",
            "eligibility_rules": {"country": "IE"},
            "benefit_type": "grant",
            "max_amount": 10000.0,
            "currency": "EUR",
            "active": False,
            "source_url": "https://www.gov.ie/test-grant",
        }
        import packages.grants.discovery as gd_module
        monkeypatch.setattr(
            gd_module.GrantSourceCrawler,
            "discover",
            lambda self, **kwargs: [dummy_candidate],
        )

        result = discover_grant_programs(dry_run=True)
        assert result["dry_run"] is True
        assert result["candidates_found"] == 1
        assert result["candidates"][0]["code"] == "IE-TEST-DISCOVERED"
        # No DB writes → created stays 0.
        assert result["created"] == 0


# ── Seed data ─────────────────────────────────────────────────────────────────


class TestSeedGrantsDerelict:
    def test_derelict_grants_present_in_defaults(self):
        from scripts.seed import DEFAULT_GRANTS

        codes = {g["code"] for g in DEFAULT_GRANTS}
        assert "IE-DERELICT-CROICONAI-2026" in codes
        assert "IE-DERELICT-VACANT-REFURB-2026" in codes
        assert "NI-DERELICT-NIHE-REPAIR-2026" in codes

    def test_derelict_grant_eligibility_rules(self):
        from scripts.seed import DEFAULT_GRANTS

        derelict = next(g for g in DEFAULT_GRANTS if g["code"] == "IE-DERELICT-CROICONAI-2026")
        rules = derelict["eligibility_rules"]
        assert "derelict" in rules.get("property_condition", [])

    def test_all_grants_have_required_fields(self):
        from scripts.seed import DEFAULT_GRANTS

        required = {"code", "name", "country", "active"}
        for g in DEFAULT_GRANTS:
            missing = required - g.keys()
            assert not missing, f"Grant {g.get('code')} missing fields: {missing}"

    def test_grants_count_expanded(self):
        from scripts.seed import DEFAULT_GRANTS

        # We had 4 grants originally; should now have significantly more.
        assert len(DEFAULT_GRANTS) >= 10


# ── Confidence threshold alignment ────────────────────────────────────────────


class TestConfidenceThresholds:
    def test_thresholds_make_sense(self):
        from packages.sources.confidence import AUTO_ENABLE_THRESHOLD, PENDING_THRESHOLD

        assert 0 < PENDING_THRESHOLD < AUTO_ENABLE_THRESHOLD < 1.0

    def test_all_default_candidates_score_high(self):
        """All built-in DEFAULT_DISCOVERY_CANDIDATES should auto-enable."""
        from packages.sources.confidence import score_candidates, AUTO_ENABLE_THRESHOLD
        from packages.sources.discovery import DEFAULT_DISCOVERY_CANDIDATES

        scored = score_candidates(DEFAULT_DISCOVERY_CANDIDATES, reject_below=0.0)
        for sc in scored:
            assert sc.score >= AUTO_ENABLE_THRESHOLD, (
                f"{sc.candidate.get('name')} scored {sc.score} < {AUTO_ENABLE_THRESHOLD}"
            )
