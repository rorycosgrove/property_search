# Correctness Contract

This document is the single authoritative definition of what "goal achieved"
means for the Irish Property Research Dashboard.  It is the release gate every
engineer must consult before shipping.

**Status: Active gating document — do not weaken thresholds without team sign-off.**

---

## Goal Statement

> "A comprehensive web-based platform for researching properties to buy across
> Ireland (Republic + Northern Ireland). Aggregates listings from multiple
> sources, provides map visualisation, price tracking, alerts, comparative
> analysis, and AI-powered insights."

"Comprehensive" and "reliable" are load-bearing words.  This contract makes
them measurable.

---

## Metrics and Thresholds

| Metric | Formula | Passing Threshold | Measurement Cadence |
|--------|---------|-------------------|---------------------|
| **Capture Rate** | `new / total_fetched` per source, 7-day rolling | ≥ 95 % for each active source | Weekly via `scripts/dev/check_capture_rate.py` |
| **Freshness SLA** | Proportion of enabled sources with `last_success_at` within 1.5× `poll_interval_seconds` | 100 % | After every scrape cycle; API: `GET /api/v1/admin/sources/freshness` |
| **Parse Fail Rate** | `parse_failed / total_fetched` per source, 7-day rolling | < 5 % | Weekly; flagged in `check_capture_rate.py` output |
| **Dedup Conflict Rate** | `dedup_conflicts / total_fetched` per source, 7-day rolling | < 10 % | Weekly |
| **Alert Precision** | Manual spot-check: proportion of generated alerts matching user saved-search criteria | ≥ 99 % | Monthly; min. 100 alerts sampled |
| **API Error Rate** | HTTP 5xx responses / total API responses, 24-hour rolling | < 2 % | Continuous; CloudWatch metric |
| **LLM Enrichment Success Rate** | `llm_enrichment_complete` / (`llm_enrichment_complete` + `llm_enrichment_failed` + `llm_enrichment_skipped[reason!=llm_disabled]`), 24-hour rolling | ≥ 95 % when LLM is enabled | Daily; `GET /api/v1/admin/backend-logs/summary` |
| **Chat Citation Coverage (24h)** | `assistant_messages_with_citations / assistant_messages` | ≥ 0.80 when sample size ≥ 10 | Continuous; `GET /api/v1/health/quality-gates` |
| **Chat p95 Latency (24h)** | p95 of `conversation_messages.processing_time_ms` for assistant messages | ≤ 4500 ms when sample size ≥ 10 | Continuous; `GET /api/v1/health/quality-gates` |

---

## Log Events Required for Measurement

The following `event_type` values in `backend_logs` provide the raw data for
the metrics above.  Each must be present in the DB for measurement to work.

| event_type | When emitted | Key context fields |
|---|---|---|
| `scrape_source_complete` | Every successful source scrape | `new`, `updated`, `parse_failed`, `price_unchanged`, `dedup_conflicts`, `total_fetched`, `new_external_ids_sample` |
| `scrape_source_failed` | Source scrape exception | `source_name`, `error` |
| `source_freshness_stale` | check_source_freshness() finds stale/never-polled | `stale`, `never_polled`, counts |
| `property_dedup_conflict_skipped` | IntegrityError during insert | `source_url`, `external_id`, `content_hash` |
| `geocode_failed` | Geocoder returns null | `address`, `county` |
| `llm_enrichment_complete` / `_failed` / `_skipped` | LLM pipeline result | `property_id`, `reason` |
| `alert_evaluation_complete` | Alert engine run | `search_alerts`, `price_alerts` |

---

## Measurement Commands

```bash
# Capture rate — last 7 days
python scripts/dev/check_capture_rate.py --hours 168

# Freshness — right now
curl http://localhost:8000/api/v1/admin/sources/freshness | python -m json.tool

# Backend health summary — last 24h
curl http://localhost:8000/api/v1/admin/logs/health | python -m json.tool

# Product quality gates (AI citation + latency + backend errors)
curl http://localhost:8000/api/v1/health/quality-gates | python -m json.tool

# Error log review
curl "http://localhost:8000/api/v1/admin/backend-logs?hours=24&level=ERROR&limit=50" | python -m json.tool
```

---

## Definition of Goal Achieved

The project is **goal achieved** when **all** of the following are true for
**two consecutive calendar weeks**:

1. Capture Rate ≥ 95 % for every active source.
2. Freshness SLA: 0 stale or never-polled enabled sources at time of measurement.
3. Parse Fail Rate < 5 % per source.
4. Dedup Conflict Rate < 10 % per source.
5. API Error Rate < 2 %.
6. All integration tests in `tests/test_ingestion_pipeline.py` pass in CI.
7. Alert Precision spot-check ≥ 99 % (monthly verification).

Until all seven criteria pass for two weeks straight, the project status is
**in progress** regardless of how many features are implemented.

---

## Stop-the-Line Rule

If Capture Rate drops below 90 % for any active source **for 24 hours**:

- Pause all non-critical deploys.
- Assign a DRI within 2 hours.
- Require a post-mortem documenting root cause within 72 hours of resolution.
- Resume normal development only after the cause is fixed and validated.

---

## DRI Assignments (update each sprint)

| Metric | Current DRI |
|--------|-------------|
| Capture Rate | Unassigned |
| Freshness SLA | Unassigned |
| Parse Fail Rate | Unassigned |
| Alert Precision | Unassigned |
| API Error Rate | Unassigned |

---

## Revision History

| Date | Change |
|------|--------|
| 2026-03-22 | Added product quality-gates metrics and `/api/v1/health/quality-gates` measurement endpoint |
| 2026-03-16 | Initial contract established |
