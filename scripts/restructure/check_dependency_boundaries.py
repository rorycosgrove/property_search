from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))")
TS_IMPORT_RE = re.compile(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]")


def python_violations() -> list[str]:
    violations: list[str] = []

    for file_path in (ROOT / "packages").rglob("*.py"):
        rel = file_path.relative_to(ROOT).as_posix()
        for line_no, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
            match = PY_IMPORT_RE.match(line)
            if not match:
                continue

            imported = match.group(1) or match.group(2) or ""
            if imported.startswith("apps"):
                violations.append(f"{rel}:{line_no} packages cannot import apps ({imported})")

            if rel.startswith("packages/shared/") and imported.startswith("packages."):
                if not imported.startswith("packages.shared"):
                    violations.append(f"{rel}:{line_no} shared cannot depend on higher layer ({imported})")

    return violations


def web_violations() -> list[str]:
    violations: list[str] = []
    web_root = ROOT / "web" / "src"

    if not web_root.exists():
        return violations

    for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
        for file_path in web_root.rglob(ext):
            rel = file_path.relative_to(ROOT).as_posix()
            for line_no, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
                match = TS_IMPORT_RE.match(line)
                if not match:
                    continue

                imported = match.group(1)
                if imported.startswith("apps/") or "/apps/" in imported:
                    violations.append(f"{rel}:{line_no} web cannot import apps ({imported})")

    return violations


def main() -> int:
    violations = python_violations() + web_violations()
    if violations:
        print("Dependency boundary violations found:")
        for item in violations:
            print(f"- {item}")
        return 1

    print("Dependency boundary checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
