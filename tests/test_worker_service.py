"""Tests for worker service compatibility shims."""

from packages.worker import service


def test_service_scrape_all_sources_delegates_to_tasks(monkeypatch):
    calls = []

    def fake_task_scrape_all_sources(force=False):
        calls.append(force)
        return {"status": "delegated", "force": force}

    monkeypatch.setattr("apps.worker.tasks.scrape_all_sources", fake_task_scrape_all_sources)

    result = service.scrape_all_sources(force=True)

    assert result == {"status": "delegated", "force": True}
    assert calls == [True]


def test_service_evaluate_alerts_delegates_to_tasks(monkeypatch):
    calls = []

    def fake_task_evaluate_alerts():
        calls.append(True)
        return {"search_alerts": 2, "price_alerts": 1}

    monkeypatch.setattr("apps.worker.tasks.evaluate_alerts", fake_task_evaluate_alerts)

    result = service.evaluate_alerts()

    assert result == {"search_alerts": 2, "price_alerts": 1}
    assert calls == [True]


def test_service_enrich_property_llm_delegates_to_tasks(monkeypatch):
    calls = []

    def fake_task_enrich_property_llm(property_id):
        calls.append(property_id)
        return {"property_id": property_id, "enriched": True}

    monkeypatch.setattr("apps.worker.tasks.enrich_property_llm", fake_task_enrich_property_llm)

    result = service.enrich_property_llm("prop-1")

    assert result == {"property_id": "prop-1", "enriched": True}
    assert calls == ["prop-1"]


def test_service_enrich_batch_llm_delegates_to_tasks(monkeypatch):
    calls = []

    def fake_task_enrich_batch_llm(limit):
        calls.append(limit)
        return {"dispatched": limit}

    monkeypatch.setattr("apps.worker.tasks.enrich_batch_llm", fake_task_enrich_batch_llm)

    result = service.enrich_batch_llm(7)

    assert result == {"dispatched": 7}
    assert calls == [7]


def test_service_cleanup_old_alerts_delegates_to_tasks(monkeypatch):
    calls = []

    def fake_task_cleanup_old_alerts(days):
        calls.append(days)
        return {"deleted": 5}

    monkeypatch.setattr("apps.worker.tasks.cleanup_old_alerts", fake_task_cleanup_old_alerts)

    result = service.cleanup_old_alerts(30)

    assert result == {"deleted": 5}
    assert calls == [30]
