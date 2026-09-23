#!/usr/bin/env python3
"""Report dependency updates without modifying repository source files.

Checks: direct PyPI dependencies in pyproject.toml, dev-group pins, the uv
version pin, GitHub Actions `uses:` pins (40-char SHA), and `uvx` tool pins
in workflows. Prints a JSON report; exit 0 always (report-only).

See docs/dependency-updates.md for the update procedure.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parents[1]
_ACTION = re.compile(r"uses:\s*([\w.-]+/[\w.-]+)@([0-9a-f]{40})(?:\s*#\s*(v[\w.-]+))?")
_UVX = re.compile(r"uvx\s+([\w.-]+)@([\w.]+)")
PYPI_JSON = "https://pypi.org/pypi/{name}/json"
GITHUB_TAGS = "https://api.github.com/repos/{repo}/tags?per_page=10"
GITHUB_COMMITS = "https://api.github.com/repos/{repo}/commits?per_page=1"


@dataclass(frozen=True)
class Status:
    name: str
    current: str
    latest: str
    source: str
    outdated: bool
    note: str = ""


def _fetch_json(url: str) -> Any:
    request = Request(url, headers={"User-Agent": "mech-dep-check"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _pypi_latest(name: str) -> str | None:
    try:
        data = _fetch_json(PYPI_JSON.format(name=name))
    except Exception:
        return None
    return str(data.get("info", {}).get("version") or "") or None


def project_dependencies() -> list[tuple[str, str]]:
    """(name, pinned-or-floor version) from pyproject dependencies + dev group."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    found: list[tuple[str, str]] = []

    def add(raw: str) -> None:
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*([<>=!~].*)?$", raw.strip())
        if match is None:
            return
        name = match.group(1)
        spec = (match.group(2) or "").strip()
        version = ""
        if spec.startswith("=="):
            version = spec.removeprefix("==").strip()
        else:
            floor = re.search(r">=\s*([\w.]+)", spec)
            version = floor.group(1) if floor else ""
        found.append((name, version))

    for dep in pyproject["project"].get("dependencies", []):
        add(dep)
    for dep in pyproject.get("dependency-groups", {}).get("dev", []):
        add(dep)
    return found


def uv_version_pin() -> str | None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return pyproject.get("tool", {}).get("uv", {}).get("required-version")


def check_pypi() -> list[Status]:
    statuses: list[Status] = []
    for name, current in project_dependencies():
        latest = _pypi_latest(name)
        if latest is None:
            statuses.append(Status(name, current, "?", "pypi", False, "fetch failed"))
            continue
        outdated = False
        note = ""
        if current:
            try:
                outdated = Version(latest) > Version(current)
            except InvalidVersion:
                note = "unparseable version"
        else:
            note = "unpinned"
        statuses.append(Status(name, current or "-", latest, "pypi", outdated, note))
    return statuses


def check_uv() -> list[Status]:
    current = (uv_version_pin() or "").removeprefix("==")
    latest = _pypi_latest("uv")
    outdated = latest is not None and bool(current) and Version(latest) > Version(current)
    return [Status("uv", current or "-", latest or "?", "pypi", outdated)]


def workflow_files() -> list[Path]:
    directory = ROOT / ".github" / "workflows"
    return sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))


def _github_latest_tag(repo: str) -> str | None:
    try:
        tags = _fetch_json(GITHUB_TAGS.format(repo=repo))
    except Exception:
        return None
    if not isinstance(tags, list) or not tags:
        return None
    first = cast(dict[str, Any], tags[0])
    name = first.get("name")
    return str(name or "") or None


def check_actions() -> list[Status]:
    statuses: list[Status] = []
    seen: set[str] = set()
    for workflow in workflow_files():
        text = workflow.read_text(encoding="utf-8")
        for repo, _sha, comment in _ACTION.findall(text):
            key = f"{repo}@{comment or 'sha'}"
            if key in seen:
                continue
            seen.add(key)
            latest = _github_latest_tag(repo)
            outdated = bool(comment and latest) and latest != comment
            statuses.append(
                Status(
                    repo,
                    comment or "sha-pinned",
                    latest or "?",
                    "github-actions",
                    outdated,
                    "" if comment else "no version comment",
                )
            )
        for tool, pin in _UVX.findall(text):
            latest = _pypi_latest(tool)
            outdated = bool(latest) and latest != pin
            statuses.append(Status(f"uvx:{tool}", pin, latest or "?", "pypi", outdated))
    return statuses


def main() -> int:
    report = {
        "pypi": [asdict(s) for s in check_pypi()],
        "uv": [asdict(s) for s in check_uv()],
        "actions": [asdict(s) for s in check_actions()],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
