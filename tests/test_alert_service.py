from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from packages.alerts.service import (
    AlertNotFoundError,
    acknowledge_alert_payload,
    acknowledge_all_payload,
    alert_stats_payload,
    list_alerts_payload,
    unread_count_payload,
)


class _FakeAlertRepo:
    def __init__(self, items=None, total=0, stats=None, count=0, acknowledge_result=True, acknowledge_all_count=0):
        self._items = items or []
        self._total = total
        self._stats = stats or {}
        self._count = count
        self._acknowledge_result = acknowledge_result
        self._acknowledge_all_count = acknowledge_all_count
        self.last_list_params = None
        self.last_acknowledge_id = None

    def list_alerts(self, *, page, per_page, alert_type, acknowledged):
        self.last_list_params = {
            "page": page,
            "per_page": per_page,
            "alert_type": alert_type,
            "acknowledged": acknowledged,
        }
        return self._items, self._total

    def get_stats(self):
        return self._stats

    def count_unacknowledged(self):
        return self._count

    def acknowledge(self, alert_id):
        self.last_acknowledge_id = alert_id
        if not self._acknowledge_result:
            return None
        return SimpleNamespace(id=alert_id)

    def acknowledge_all(self):
        return self._acknowledge_all_count


class TestAlertServicePayloads:
    def test_list_alerts_payload_serializes_response(self):
        alert = SimpleNamespace(
            id="a-1",
            alert_type="new_listing",
            title="New listing",
            severity="low",
            property_id="p-1",
            saved_search_id="s-1",
            metadata_json={"foo": "bar"},
            acknowledged=False,
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
        repo = _FakeAlertRepo(items=[alert], total=1)

        payload = list_alerts_payload(
            repo=repo,
            page=1,
            size=20,
            alert_type="new_listing",
            acknowledged=False,
        )

        assert payload["total"] == 1
        assert payload["items"][0]["id"] == "a-1"
        assert payload["items"][0]["created_at"] == "2026-03-01T00:00:00+00:00"
        assert repo.last_list_params == {
            "page": 1,
            "per_page": 20,
            "alert_type": "new_listing",
            "acknowledged": False,
        }

    def test_alert_stats_payload_delegates(self):
        repo = _FakeAlertRepo(stats={"by_type": [], "total_unacknowledged": 2})

        payload = alert_stats_payload(repo=repo)

        assert payload["total_unacknowledged"] == 2

    def test_unread_count_payload_delegates(self):
        repo = _FakeAlertRepo(count=5)

        payload = unread_count_payload(repo=repo)

        assert payload == {"count": 5}

    def test_acknowledge_alert_payload_raises_for_missing_alert(self):
        repo = _FakeAlertRepo(acknowledge_result=False)

        with pytest.raises(AlertNotFoundError):
            acknowledge_alert_payload(repo=repo, alert_id="missing")

    def test_acknowledge_alert_payload_success(self):
        repo = _FakeAlertRepo(acknowledge_result=True)

        payload = acknowledge_alert_payload(repo=repo, alert_id="a-2")

        assert payload == {"acknowledged": True}
        assert repo.last_acknowledge_id == "a-2"

    def test_acknowledge_all_payload_success(self):
        repo = _FakeAlertRepo(acknowledge_all_count=7)

        payload = acknowledge_all_payload(repo=repo)

        assert payload == {"acknowledged": 7}
