from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".dev-runtime"
OUT_FILE = OUT_DIR / "stage0_baseline.json"


def run(cmd: list[str] | str, cwd: Path, shell: bool = False) -> dict[str, object]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=shell)
    rendered = cmd if isinstance(cmd, str) else " ".join(cmd)
    return {
        "command": rendered,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    npm_lint_cmd: list[str] | str = ["npm", "run", "lint"]
    npm_build_cmd: list[str] | str = ["npm", "run", "build"]
    npm_shell = False

    if os.name == "nt":
        npm_lint_cmd = "npm run lint"
        npm_build_cmd = "npm run build"
        npm_shell = True

    baseline = {
        "captured_at": datetime.now(UTC).isoformat(),
        "git_branch": run(["git", "branch", "--show-current"], ROOT),
        "backend_tests": run(["python", "-m", "pytest", "-q"], ROOT),
        "frontend_lint": run(npm_lint_cmd, ROOT / "web", shell=npm_shell),
        "frontend_build": run(npm_build_cmd, ROOT / "web", shell=npm_shell),
    }

    OUT_FILE.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    print(str(OUT_FILE))


if __name__ == "__main__":
    main()
