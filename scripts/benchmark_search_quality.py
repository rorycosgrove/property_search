"""Run lightweight, repeatable search quality benchmarks against local data.

The benchmark is intentionally heuristic-based so it can run quickly in local
dev and CI-like environments without a manually labeled relevance dataset.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Iterable

from sqlalchemy import select

from packages.shared.constants import (
    DEFAULT_PAGE_SIZE,
    SEARCH_BENCHMARK_MIN_RESULT_COVERAGE,
    SEARCH_BENCHMARK_MIN_TOP3_OVERLAP,
    SEARCH_BENCHMARK_MIN_TOP_OVERLAP,
)
from packages.shared.schemas import PropertyFilters
from packages.storage.database import get_session
from packages.storage.models import Property
from packages.storage.repositories import PropertyRepository


TOKEN_RE = re.compile(r"[a-zA-Z0-9]{3,}")
ABBREVIATIONS = {
    "street": "st",
    "road": "rd",
    "avenue": "ave",
    "county": "co",
    "apartment": "apt",
}


@dataclass
class BenchmarkGates:
    min_result_coverage: float = SEARCH_BENCHMARK_MIN_RESULT_COVERAGE
    min_top_overlap: float = SEARCH_BENCHMARK_MIN_TOP_OVERLAP
    min_top3_overlap: float = SEARCH_BENCHMARK_MIN_TOP3_OVERLAP


@dataclass
class QueryBenchmarkResult:
    query: str
    results: int
    top_overlap: float
    top3_avg_overlap: float


def _tokenize(value: str | None) -> set[str]:
    if not value:
        return set()
    return {tok.lower() for tok in TOKEN_RE.findall(value)}


def _extract_query_candidates(title: str | None, address: str | None, county: str | None) -> list[str]:
    candidates = []
    if county:
        candidates.append(county.strip())

    for token in list(_tokenize(title)) + list(_tokenize(address)):
        if token.isdigit():
            continue
        if token in {"road", "street", "house", "apartment", "county"}:
            continue
        candidates.append(token)
    return candidates


def _make_challenging_query(query: str) -> str:
    tokens = query.lower().split()
    if not tokens:
        return query

    transformed: list[str] = []
    for idx, token in enumerate(tokens):
        if token in ABBREVIATIONS:
            transformed.append(ABBREVIATIONS[token])
            continue

        if idx == 0 and len(token) >= 5:
            # mild typo to exercise trigram tolerance (e.g. dublin -> dubln)
            pos = max(token.rfind("a"), token.rfind("e"), token.rfind("i"), token.rfind("o"), token.rfind("u"))
            if 1 <= pos < len(token) - 1:
                transformed.append(token[:pos] + token[pos + 1 :])
            else:
                transformed.append(token[:-1])
            continue

        transformed.append(token)

    return " ".join(transformed)


def _query_overlap_score(query: str, title: str | None, address: str | None, description: str | None) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0

    doc_tokens = _tokenize(title) | _tokenize(address) | _tokenize(description)
    if not doc_tokens:
        return 0.0

    return len(query_tokens & doc_tokens) / len(query_tokens)


def _derive_queries(sample_rows: Iterable[tuple[str | None, str | None, str | None]], limit: int) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()

    for title, address, county in sample_rows:
        for candidate in _extract_query_candidates(title, address, county):
            q = candidate.lower().strip()
            if len(q) < 3 or q in seen:
                continue
            seen.add(q)
            queries.append(q)
            if len(queries) >= limit:
                return queries
    return queries


def _build_query_set(auto_queries: list[str], mode: str) -> list[str]:
    if mode == "auto":
        return auto_queries

    if mode == "challenging":
        return [_make_challenging_query(q) for q in auto_queries]

    # mixed
    mixed: list[str] = []
    seen: set[str] = set()
    for q in auto_queries:
        for candidate in (q, _make_challenging_query(q)):
            c = candidate.strip().lower()
            if c and c not in seen:
                seen.add(c)
                mixed.append(c)
    return mixed


def _load_queries_file(path: str) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"queries file not found: {path}")

    queries: list[str] = []
    seen: set[str] = set()
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        query = line.lower()
        if query in seen:
            continue
        seen.add(query)
        queries.append(query)
    return queries


def _run_query_benchmark(repo: PropertyRepository, query: str, size: int) -> QueryBenchmarkResult:
    filters = PropertyFilters(
        keywords=[query],
        sort_by="relevance",
        sort_order="desc",
        page=1,
        per_page=size,
    )
    items, _total = repo.list_properties(filters)

    if not items:
        return QueryBenchmarkResult(query=query, results=0, top_overlap=0.0, top3_avg_overlap=0.0)

    overlaps = [
        _query_overlap_score(query, item.title, item.address, item.description)
        for item in items[:3]
    ]
    top_overlap = overlaps[0] if overlaps else 0.0
    top3_avg = mean(overlaps) if overlaps else 0.0
    return QueryBenchmarkResult(
        query=query,
        results=len(items),
        top_overlap=round(top_overlap, 4),
        top3_avg_overlap=round(top3_avg, 4),
    )


def _evaluate_gates(summary: dict, gates: BenchmarkGates) -> dict[str, bool]:
    return {
        "result_coverage": float(summary.get("result_coverage", 0.0)) >= gates.min_result_coverage,
        "avg_top_overlap": float(summary.get("avg_top_overlap", 0.0)) >= gates.min_top_overlap,
        "avg_top3_overlap": float(summary.get("avg_top3_overlap", 0.0)) >= gates.min_top3_overlap,
    }


def run_benchmark(
    *,
    queries: list[str] | None,
    queries_file: str | None,
    query_count: int,
    size: int,
    query_set: str,
) -> dict:
    with get_session() as session:
        repo = PropertyRepository(session)

        selected_queries = _load_queries_file(queries_file) if queries_file else []
        if not selected_queries:
            selected_queries = [q.strip().lower() for q in (queries or []) if q.strip()]
        if not selected_queries:
            rows = session.execute(
                select(Property.title, Property.address, Property.county)
                .where(Property.status.in_(["new", "active", "price_changed"]))
                .order_by(Property.updated_at.desc())
                .limit(max(query_count * 4, 40))
            ).all()
            auto_queries = _derive_queries(rows, query_count)
            selected_queries = _build_query_set(auto_queries, query_set)

        results = [_run_query_benchmark(repo, q, size) for q in selected_queries]

    with_results = [r for r in results if r.results > 0]
    top_good = [r for r in with_results if r.top_overlap >= 0.5]
    top_ok = [r for r in with_results if r.top_overlap >= 0.3]

    summary = {
        "queries_run": len(results),
        "queries_with_results": len(with_results),
        "result_coverage": round((len(with_results) / len(results)) if results else 0.0, 4),
        "top_overlap_ge_0_5": len(top_good),
        "top_overlap_ge_0_3": len(top_ok),
        "avg_top_overlap": round(mean([r.top_overlap for r in with_results]), 4) if with_results else 0.0,
        "avg_top3_overlap": round(mean([r.top3_avg_overlap for r in with_results]), 4) if with_results else 0.0,
    }

    return {
        "summary": summary,
        "queries": [asdict(r) for r in results],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark property search relevance.")
    parser.add_argument(
        "--queries",
        type=str,
        default="",
        help="Comma-separated custom queries (optional).",
    )
    parser.add_argument(
        "--queries-file",
        type=str,
        default="",
        help="Path to newline-delimited query list (comments with # allowed).",
    )
    parser.add_argument(
        "--query-count",
        type=int,
        default=12,
        help="How many auto-derived queries to benchmark when --queries is omitted.",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="How many results per query to evaluate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print only JSON output.",
    )
    parser.add_argument(
        "--query-set",
        choices=["auto", "challenging", "mixed"],
        default="mixed",
        help="How to generate queries when --queries is omitted.",
    )
    parser.add_argument(
        "--enforce-gates",
        action="store_true",
        help="Exit non-zero when benchmark summary is below configured gates.",
    )
    args = parser.parse_args()

    query_list = [part.strip() for part in args.queries.split(",") if part.strip()]
    payload = run_benchmark(
        queries=query_list,
        queries_file=args.queries_file or None,
        query_count=max(1, args.query_count),
        size=max(1, args.size),
        query_set=args.query_set,
    )

    gates = BenchmarkGates()
    gate_status = _evaluate_gates(payload["summary"], gates)
    payload["gates"] = {
        "thresholds": asdict(gates),
        "status": gate_status,
        "passed": all(gate_status.values()),
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        if args.enforce_gates and not payload["gates"]["passed"]:
            sys.exit(2)
        return

    summary = payload["summary"]
    print("Search Quality Benchmark")
    print("========================")
    print(f"queries_run: {summary['queries_run']}")
    print(f"queries_with_results: {summary['queries_with_results']}")
    print(f"result_coverage: {summary['result_coverage']}")
    print(f"top_overlap_ge_0_5: {summary['top_overlap_ge_0_5']}")
    print(f"top_overlap_ge_0_3: {summary['top_overlap_ge_0_3']}")
    print(f"avg_top_overlap: {summary['avg_top_overlap']}")
    print(f"avg_top3_overlap: {summary['avg_top3_overlap']}")
    print(f"gates_passed: {payload['gates']['passed']}")
    print()
    print(json.dumps(payload, indent=2))

    if args.enforce_gates and not payload["gates"]["passed"]:
        sys.exit(2)


if __name__ == "__main__":
    main()