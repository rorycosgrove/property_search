from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from packages.saved_searches.service import (
    SavedSearchNotFoundError,
    create_saved_search_payload,
    delete_saved_search_payload,
    get_saved_search_payload,
    list_saved_searches_payload,
    saved_search_to_dict,
    update_saved_search_payload,
)


class _FakeSavedSearchRepo:
    def __init__(self, items=None, created=None, get_by_id_result=None, updated=None):
        self._items = items or []
        self._created = created
        self._get_by_id_result = get_by_id_result
        self._updated = updated
        self.create_kwargs = None
        self.update_kwargs = None
        self.deleted_id = None

    def get_all(self):
        return self._items

    def create(self, **kwargs):
        self.create_kwargs = kwargs
        return self._created

    def get_by_id(self, _search_id):
        return self._get_by_id_result

    def update(self, search_id, **kwargs):
        self.update_kwargs = {"search_id": search_id, **kwargs}
        return self._updated

    def delete(self, search_id):
        self.deleted_id = search_id


class _Criteria:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return self._payload


class _CreateData:
    def __init__(self):
        self.name = "My Search"
        self.criteria = _Criteria({"county": "Dublin"})
        self.notify_new_listings = True
        self.notify_price_drops = True
        self.notify_method = "in_app"
        self.email = "test@example.com"


class _UpdateData:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, exclude_unset=True):
        return self._payload


def _sample_search(search_id="ss-1"):
    return SimpleNamespace(
        id=search_id,
        name="Search",
        criteria={"county": "Dublin"},
        notify_new_listings=True,
        notify_price_drops=True,
        notify_method="in_app",
        email="test@example.com",
        is_active=True,
        last_matched_at=datetime(2026, 3, 1, tzinfo=UTC),
        created_at=datetime(2026, 3, 1, tzinfo=UTC),
        updated_at=datetime(2026, 3, 2, tzinfo=UTC),
    )


class TestSavedSearchService:
    def test_saved_search_to_dict_serializes_datetime_fields(self):
        payload = saved_search_to_dict(_sample_search())
        assert payload["id"] == "ss-1"
        assert payload["created_at"] == "2026-03-01T00:00:00+00:00"

    def test_list_saved_searches_payload(self):
        repo = _FakeSavedSearchRepo(items=[_sample_search("ss-1"), _sample_search("ss-2")])
        payload = list_saved_searches_payload(repo=repo)
        assert len(payload) == 2
        assert payload[1]["id"] == "ss-2"

    def test_create_saved_search_payload_uses_expected_repo_args(self):
        created = _sample_search("ss-created")
        repo = _FakeSavedSearchRepo(created=created)

        payload = create_saved_search_payload(repo=repo, data=_CreateData())

        assert payload["id"] == "ss-created"
        assert repo.create_kwargs["name"] == "My Search"
        assert repo.create_kwargs["criteria"] == {"county": "Dublin"}
        assert repo.create_kwargs["is_active"] is True

    def test_get_saved_search_payload_raises_when_missing(self):
        repo = _FakeSavedSearchRepo(get_by_id_result=None)
        with pytest.raises(SavedSearchNotFoundError):
            get_saved_search_payload(repo=repo, search_id="missing")

    def test_update_saved_search_payload_maps_criteria(self):
        existing = _sample_search("ss-1")
        updated = _sample_search("ss-1")
        repo = _FakeSavedSearchRepo(get_by_id_result=existing, updated=updated)
        data = _UpdateData({"criteria": _Criteria({"min_price": 200000})})

        payload = update_saved_search_payload(repo=repo, search_id="ss-1", data=data)

        assert payload["id"] == "ss-1"
        assert repo.update_kwargs["search_id"] == "ss-1"
        assert repo.update_kwargs["criteria"] == {"min_price": 200000}

    def test_delete_saved_search_payload_raises_when_missing(self):
        repo = _FakeSavedSearchRepo(get_by_id_result=None)
        with pytest.raises(SavedSearchNotFoundError):
            delete_saved_search_payload(repo=repo, search_id="missing")

    def test_delete_saved_search_payload_calls_repo_delete(self):
        repo = _FakeSavedSearchRepo(get_by_id_result=_sample_search("ss-1"))

        delete_saved_search_payload(repo=repo, search_id="ss-1")

        assert repo.deleted_id == "ss-1"
