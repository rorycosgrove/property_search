from __future__ import annotations

from typing import Any


class SavedSearchServiceError(Exception):
    """Base exception for saved-search domain services."""


class SavedSearchNotFoundError(SavedSearchServiceError):
    def __init__(self, search_id: str):
        self.search_id = search_id
        super().__init__(f"saved search not found: {search_id}")


def saved_search_to_dict(search: Any) -> dict[str, Any]:
    return {
        "id": str(search.id),
        "name": search.name,
        "criteria": search.criteria,
        "notify_new_listings": search.notify_new_listings,
        "notify_price_drops": search.notify_price_drops,
        "notify_method": search.notify_method,
        "email": search.email,
        "is_active": search.is_active,
        "last_matched_at": search.last_matched_at.isoformat() if search.last_matched_at else None,
        "created_at": search.created_at.isoformat() if search.created_at else None,
        "updated_at": search.updated_at.isoformat() if search.updated_at else None,
    }


def list_saved_searches_payload(*, repo: Any) -> list[dict[str, Any]]:
    return [saved_search_to_dict(search) for search in repo.get_all()]


def create_saved_search_payload(*, repo: Any, data: Any) -> dict[str, Any]:
    search = repo.create(
        name=data.name,
        criteria=data.criteria.model_dump() if data.criteria else {},
        notify_new_listings=data.notify_new_listings,
        notify_price_drops=data.notify_price_drops,
        notify_method=data.notify_method,
        email=data.email,
        is_active=True,
    )
    return saved_search_to_dict(search)


def get_saved_search_payload(*, repo: Any, search_id: str) -> dict[str, Any]:
    search = repo.get_by_id(search_id)
    if not search:
        raise SavedSearchNotFoundError(search_id)
    return saved_search_to_dict(search)


def update_saved_search_payload(*, repo: Any, search_id: str, data: Any) -> dict[str, Any]:
    if not repo.get_by_id(search_id):
        raise SavedSearchNotFoundError(search_id)

    updates = data.model_dump(exclude_unset=True)
    if "criteria" in updates and updates["criteria"]:
        criteria = updates["criteria"]
        updates["criteria"] = criteria.model_dump() if hasattr(criteria, "model_dump") else criteria

    updated = repo.update(search_id, **updates)
    return saved_search_to_dict(updated)


def delete_saved_search_payload(*, repo: Any, search_id: str) -> None:
    if not repo.get_by_id(search_id):
        raise SavedSearchNotFoundError(search_id)
    repo.delete(search_id)
