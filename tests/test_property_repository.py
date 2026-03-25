from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from packages.shared.schemas import PropertyFilters
from packages.storage.repositories import PropertyRepository


class _ScalarResult(list):
    def unique(self):
        return self


class _ExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def unique(self):
        return self

    def __iter__(self):
        return iter(self._rows)


class _FakeBind:
    def __init__(self, dialect_name: str):
        self.dialect = SimpleNamespace(name=dialect_name)


class _FakeSession:
    def __init__(self, *, dialect_name: str):
        self._bind = _FakeBind(dialect_name)
        self.scalar_queries = []
        self.scalars_queries = []
        self.execute_queries = []

    def get_bind(self):
        return self._bind

    def scalar(self, query):
        self.scalar_queries.append(query)
        return 0

    def scalars(self, query):
        self.scalars_queries.append(query)
        return _ScalarResult()

    def execute(self, query):
        self.execute_queries.append(query)
        return _ExecuteResult([])


def _filters() -> PropertyFilters:
    return PropertyFilters(
        keywords=["main street"],
        sort_by="created_at",
        sort_order="desc",
        page=1,
        per_page=20,
    )


def _filters_with_sort(sort_by: str, sort_order: str = "desc") -> PropertyFilters:
    return PropertyFilters(
        keywords=["main street"],
        sort_by=sort_by,
        sort_order=sort_order,
        page=1,
        per_page=20,
    )


def test_list_properties_uses_pg_similarity_for_keywords():
    session = _FakeSession(dialect_name="postgresql")
    repo = PropertyRepository(session)

    repo.list_properties(_filters())

    query = session.scalars_queries[0]
    compiled = query.compile(dialect=postgresql.dialect())
    query_text = str(compiled).lower()

    assert "similarity(" in query_text
    assert "properties.title" in query_text
    assert "properties.address" in query_text
    assert "%main street%" in compiled.params.values()
    assert 0.2 in compiled.params.values()


def test_list_properties_with_eligible_grants_uses_pg_similarity_for_keywords():
    session = _FakeSession(dialect_name="postgresql")
    repo = PropertyRepository(session)

    repo.list_properties_with_eligible_grants(_filters())

    query = session.execute_queries[0]
    compiled = query.compile(dialect=postgresql.dialect())
    query_text = str(compiled).lower()

    assert "similarity(" in query_text
    assert "properties.title" in query_text
    assert "properties.address" in query_text
    assert 0.2 in compiled.params.values()


def test_list_properties_keeps_ilike_fallback_outside_postgres():
    session = _FakeSession(dialect_name="sqlite")
    repo = PropertyRepository(session)

    repo.list_properties(_filters())

    query = session.scalars_queries[0]
    query_text = str(query.compile()).lower()

    assert "similarity(" not in query_text
    assert "lower(properties.title) like lower" in query_text
    assert "lower(properties.address) like lower" in query_text


def test_list_properties_relevance_sort_orders_by_keyword_rank():
    session = _FakeSession(dialect_name="postgresql")
    repo = PropertyRepository(session)

    repo.list_properties(_filters_with_sort("relevance", "desc"))

    query = session.scalars_queries[0]
    compiled = query.compile(dialect=postgresql.dialect())
    query_text = str(compiled).lower()

    assert "order by" in query_text
    assert "similarity(" in query_text
    assert "properties.created_at" in query_text


def test_list_properties_with_eligible_grants_relevance_sort_orders_by_keyword_rank():
    session = _FakeSession(dialect_name="postgresql")
    repo = PropertyRepository(session)

    repo.list_properties_with_eligible_grants(_filters_with_sort("relevance", "desc"))

    query = session.execute_queries[0]
    compiled = query.compile(dialect=postgresql.dialect())
    query_text = str(compiled).lower()

    assert "order by" in query_text
    assert "similarity(" in query_text
    assert "properties.created_at" in query_text