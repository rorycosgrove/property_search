from __future__ import annotations

from pathlib import Path


def test_alembic_revision_ids_fit_version_column():
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"

    for path in versions_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("revision = "):
                continue

            quote = '"' if '"' in stripped else "'"
            revision = stripped.split(quote)[1]
            assert len(revision) <= 32, f"{path.name} revision too long: {revision}"
            break