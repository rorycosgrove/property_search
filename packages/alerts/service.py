from __future__ import annotations

from typing import Any


class AlertServiceError(Exception):
    """Base exception for alert-domain services."""


class AlertNotFoundError(AlertServiceError):
    def __init__(self, alert_id: str):
        self.alert_id = alert_id
        super().__init__(f"alert not found: {alert_id}")


def alert_to_dict(alert: Any) -> dict[str, Any]:
    return {
        "id": str(alert.id),
        "alert_type": alert.alert_type,
        "title": alert.title,
        "severity": alert.severity,
        "property_id": str(alert.property_id) if alert.property_id else None,
        "saved_search_id": str(alert.saved_search_id) if alert.saved_search_id else None,
        "metadata": alert.metadata_json,
        "acknowledged": alert.acknowledged,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


def list_alerts_payload(
    *,
    repo: Any,
    page: int,
    size: int,
    alert_type: str | None,
    acknowledged: bool | None,
) -> dict[str, Any]:
    items, total = repo.list_alerts(
        page=page,
        per_page=size,
        alert_type=alert_type,
        acknowledged=acknowledged,
    )
    return {
        "items": [alert_to_dict(item) for item in items],
        "total": total,
        "page": page,
        "size": size,
    }


def alert_stats_payload(*, repo: Any) -> dict[str, Any]:
    return repo.get_stats()


def unread_count_payload(*, repo: Any) -> dict[str, int]:
    return {"count": repo.count_unacknowledged()}


def acknowledge_alert_payload(*, repo: Any, alert_id: str) -> dict[str, bool]:
    alert = repo.acknowledge(alert_id)
    if not alert:
        raise AlertNotFoundError(alert_id)
    return {"acknowledged": True}


def acknowledge_all_payload(*, repo: Any) -> dict[str, int]:
    return {"acknowledged": repo.acknowledge_all()}
