from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from packages.storage.repositories import SoldPropertyRepository


class _ExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeBind:
    def __init__(self, dialect_name: str):
        self.dialect = SimpleNamespace(name=dialect_name)


class _FakeSession:
    def __init__(self, *, dialect_name: str, execute_rows=None, scalar_rows=None):
        self._bind = _FakeBind(dialect_name)
        self.execute_rows = execute_rows or []
        self.scalar_rows = scalar_rows or []
        self.execute_queries = []
        self.scalar_queries = []

    def get_bind(self):
        return self._bind

    def execute(self, query):
        self.execute_queries.append(query)
        rows = self.execute_rows.pop(0)
        return _ExecuteResult(rows)

    def scalars(self, query):
        self.scalar_queries.append(query)
        return self.scalar_rows


def _sold(*, sold_id: str, address: str, sale_date_value: date, county: str = "Dublin"):
    return SimpleNamespace(
        id=sold_id,
        address=address,
        address_normalized=address.lower(),
        county=county,
        price=Decimal("300000.00"),
        sale_date=sale_date_value,
        latitude=None,
        longitude=None,
    )


def test_get_confident_comparable_sold_uses_pg_similarity_query():
    sold = _sold(sold_id="sold-1", address="12 Main Street", sale_date_value=date(2025, 2, 10))
    session = _FakeSession(dialect_name="postgresql", execute_rows=[[(sold, 0.9721)]])
    repo = SoldPropertyRepository(session)

    result = repo.get_confident_comparable_sold(
        address="12 Main St",
        county="Dublin",
        fuzzy_address_hash_value="hash-1",
        limit=5,
        min_similarity=0.9,
    )

    assert result[0]["id"] == "sold-1"
    assert result[0]["match_confidence"] == "high"
    query = session.execute_queries[0]
    compiled = query.compile(dialect=postgresql.dialect())
    query_text = str(compiled).lower()

    assert "similarity(" in query_text
    assert "sold_properties.fuzzy_address_hash" in query_text
    assert "sold_properties.county" in query_text
    assert 0.9 in compiled.params.values()


def test_get_confident_comparable_sold_uses_python_fallback_outside_postgres():
    session = _FakeSession(
        dialect_name="sqlite",
        scalar_rows=[
            _sold(sold_id="sold-1", address="12 Main Street", sale_date_value=date(2025, 2, 10)),
            _sold(sold_id="sold-2", address="88 Different Road", sale_date_value=date(2025, 1, 1)),
        ],
    )
    repo = SoldPropertyRepository(session)

    result = repo.get_confident_comparable_sold(
        address="12 Main Street",
        county="Dublin",
        fuzzy_address_hash_value="hash-1",
        limit=5,
        min_similarity=0.9,
    )

    assert len(result) == 1
    assert result[0]["id"] == "sold-1"
    assert result[0]["match_method"] == "fuzzy_hash_county_address_similarity"
    assert result[0]["match_score"] >= 0.9
    assert len(session.scalar_queries) == 1