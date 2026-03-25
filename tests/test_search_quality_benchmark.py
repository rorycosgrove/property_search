from __future__ import annotations

from scripts.benchmark_search_quality import (
    BenchmarkGates,
    _build_query_set,
    _evaluate_gates,
    _load_queries_file,
    _make_challenging_query,
    _derive_queries,
    _query_overlap_score,
    _tokenize,
    run_benchmark,
)


def test_tokenize_extracts_lowercase_terms():
    tokens = _tokenize("12 Main Street, Dublin 4")
    assert "main" in tokens
    assert "street" in tokens
    assert "dublin" in tokens


def test_query_overlap_score_returns_expected_ratio():
    score = _query_overlap_score(
        "main dublin",
        "Spacious Home",
        "12 Main Street",
        "Located near Dublin city",
    )
    assert score == 1.0


def test_derive_queries_deduplicates_candidates():
    rows = [
        ("Main Street Home", "12 Main Street", "Dublin"),
        ("Main Street Apartment", "7 Main Street", "Dublin"),
    ]
    queries = _derive_queries(rows, limit=5)
    assert "dublin" in queries
    assert len(queries) == len(set(queries))


def test_make_challenging_query_applies_abbreviation_and_typo_pattern():
    query = _make_challenging_query("dublin street")
    assert query in {"dublin st", "dubln st"}


def test_build_query_set_mixed_contains_base_and_challenging():
    queries = _build_query_set(["dublin street"], mode="mixed")
    assert "dublin street" in queries
    assert any("st" in q for q in queries)


def test_evaluate_gates_flags_failures_and_passes():
    gates = BenchmarkGates(min_result_coverage=0.5, min_top_overlap=0.4, min_top3_overlap=0.3)
    summary_good = {
        "result_coverage": 0.8,
        "avg_top_overlap": 0.6,
        "avg_top3_overlap": 0.5,
    }
    summary_bad = {
        "result_coverage": 0.2,
        "avg_top_overlap": 0.6,
        "avg_top3_overlap": 0.1,
    }

    status_good = _evaluate_gates(summary_good, gates)
    status_bad = _evaluate_gates(summary_bad, gates)

    assert all(status_good.values())
    assert status_bad["result_coverage"] is False
    assert status_bad["avg_top3_overlap"] is False


def test_load_queries_file_skips_comments_and_dedupes(tmp_path):
    query_file = tmp_path / "queries.txt"
    query_file.write_text("# comments\nDublin\n\nDublin\nBlackrock\n", encoding="utf-8")

    queries = _load_queries_file(str(query_file))

    assert queries == ["dublin", "blackrock"]


def test_run_benchmark_prefers_queries_file_over_auto(monkeypatch, tmp_path):
    query_file = tmp_path / "queries.txt"
    query_file.write_text("dublin\nblackrock\n", encoding="utf-8")

    class _FakeRepo:
        def __init__(self, _session):
            pass

        def list_properties(self, _filters):
            class _Row:
                title = "Dublin Home"
                address = "Main Street"
                description = "Near city"

            return [_Row()], 1

    class _FakeSession:
        def execute(self, _query):
            class _Rows:
                def all(self):
                    return []

            return _Rows()

    class _FakeSessionCtx:
        def __enter__(self):
            return _FakeSession()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("scripts.benchmark_search_quality.get_session", lambda: _FakeSessionCtx())
    monkeypatch.setattr("scripts.benchmark_search_quality.PropertyRepository", _FakeRepo)

    payload = run_benchmark(
        queries=None,
        queries_file=str(query_file),
        query_count=5,
        size=5,
        query_set="mixed",
    )

    assert payload["summary"]["queries_run"] == 2
    assert payload["summary"]["queries_with_results"] == 2