from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROJECTS_FILE = ROOT / "workspace" / "projects.json"


def load_projects() -> list[dict[str, Any]]:
    data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    return data["projects"]


def get_project(projects: list[dict[str, Any]], project_id: str) -> dict[str, Any]:
    for project in projects:
        if project["id"] == project_id:
            return project
    raise SystemExit(f"Unknown project: {project_id}")


def run_command(command: str, cwd: Path) -> int:
    completed = subprocess.run(command, cwd=cwd, shell=True)
    return completed.returncode


def list_projects(projects: list[dict[str, Any]]) -> int:
    for project in projects:
        tags = ", ".join(project.get("tags", []))
        print(f"{project['id']:12} {project['path']:25} {project['type']:14} {tags}")
    return 0


def run_target(projects: list[dict[str, Any]], target: str, project_id: str | None) -> int:
    selected = [get_project(projects, project_id)] if project_id else projects
    failed = False

    for project in selected:
        command = project.get("commands", {}).get(target)
        if not command:
            continue

        print(f"\n==> {project['id']}:{target} ({command})")
        exit_code = run_command(command, ROOT)
        if exit_code != 0:
            print(f"FAILED: {project['id']}:{target} exit={exit_code}")
            failed = True

    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run workspace project tasks.")
    parser.add_argument("action", choices=["list", "run"], help="Action to perform")
    parser.add_argument("target", nargs="?", help="Target to run, e.g. lint/test/build")
    parser.add_argument("--project", dest="project", help="Single project id")
    args = parser.parse_args()

    projects = load_projects()

    if args.action == "list":
        return list_projects(projects)

    if not args.target:
        raise SystemExit("Target is required for action=run")

    return run_target(projects, args.target, args.project)


if __name__ == "__main__":
    raise SystemExit(main())
