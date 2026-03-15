import pytest
from unittest.mock import MagicMock
from packages.storage.repositories import PropertyRepository
from packages.storage.models import Property, PropertyPriceHistory

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

@pytest.fixture
def dummy_session():
    return DummySession()

@pytest.fixture
def repo(dummy_session):
    return PropertyRepository(dummy_session)

def test_create_records_initial_price_history(repo):
    prop = repo.create(id="p1", price=100000.0)
    price_histories = [o for o in repo.session.objects if isinstance(o, PropertyPriceHistory)]
    assert len(price_histories) == 1
    assert price_histories[0].price == 100000.0
    assert price_histories[0].price_change is None

def test_update_records_price_change(repo):
    prop = repo.create(id="p2", price=200000.0)
    repo.update("p2", price=210000.0)
    price_histories = [o for o in repo.session.objects if isinstance(o, PropertyPriceHistory)]
    assert len(price_histories) == 2
    assert price_histories[-1].price == 210000.0
    assert price_histories[-1].price_change == 10000.0
    assert price_histories[-1].price_change_pct == pytest.approx(5.0)
