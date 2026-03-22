import pytest
from unittest.mock import MagicMock
from packages.storage.repositories import PriceHistoryRepository, PropertyRepository
from packages.storage.models import Property, PropertyPriceHistory, PropertyTimelineEvent

class DummySession:
    def __init__(self):
        self.objects = []
    def add(self, obj):
        self.objects.append(obj)
    def flush(self):
        pass
    def get(self, model, id):
        for obj in self.objects:
            if isinstance(obj, model) and getattr(obj, 'id', None) == id:
                return obj
        return None
    def get_bind(self):
        """Mock get_bind for dialect detection."""
        bind = MagicMock()
        bind.dialect.name = "sqlite"
        return bind
    def begin_nested(self):
        """Mock savepoint context manager."""
        return MagicMock(__enter__=MagicMock(return_value=None), __exit__=MagicMock(return_value=False))

@pytest.fixture
def dummy_session():
    return DummySession()

@pytest.fixture
def repo(dummy_session):
    return PropertyRepository(dummy_session)

def test_create_records_initial_price_history(repo):
    prop = repo.create(id="p1", price=100000.0)
    price_histories = [o for o in repo.session.objects if isinstance(o, PropertyPriceHistory)]
    timeline_events = [o for o in repo.session.objects if isinstance(o, PropertyTimelineEvent)]
    assert len(price_histories) == 1
    assert price_histories[0].price == 100000.0
    assert price_histories[0].price_change is None
    assert len(timeline_events) == 1
    assert timeline_events[0].event_type == "asking_price_set"
    assert timeline_events[0].price == 100000.0

def test_update_records_price_change(repo):
    prop = repo.create(id="p2", price=200000.0)
    repo.update("p2", price=210000.0)
    price_histories = [o for o in repo.session.objects if isinstance(o, PropertyPriceHistory)]
    timeline_events = [o for o in repo.session.objects if isinstance(o, PropertyTimelineEvent)]
    assert len(price_histories) == 2
    assert price_histories[-1].price == 210000.0
    assert price_histories[-1].price_change == 10000.0
    assert price_histories[-1].price_change_pct == pytest.approx(5.0)
    assert len(timeline_events) == 2
    assert timeline_events[-1].event_type == "asking_price_changed"
    assert timeline_events[-1].price == 210000.0
    assert timeline_events[-1].price_change == 10000.0


def test_price_history_list_for_property_delegates_to_existing_query_method():
    session = MagicMock()
    repo = PriceHistoryRepository(session)
    expected = [MagicMock(spec=PropertyPriceHistory)]
    repo.get_for_property = MagicMock(return_value=expected)

    result = repo.list_for_property("p1")

    assert result == expected
    repo.get_for_property.assert_called_once_with("p1")
