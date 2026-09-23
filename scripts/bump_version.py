"""Bump the mech plugin version across every version-bearing file.

Updates plugins/mech/.plugin/plugin.json, pyproject.toml, and the mech-agent
package entry in uv.lock. Fails closed if the source files disagree on the
current version.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

_PATTERNS = {
    "plugins/mech/.plugin/plugin.json": re.compile(r'"version":\s*"([^"]+)"'),
    "pyproject.toml": re.compile(r'(?m)^version = "([^"]+)"'),
}

_SETTERS = {
    "plugins/mech/.plugin/plugin.json": re.compile(r'("version":\s*")[^"]+(")'),
    "pyproject.toml": re.compile(r'(?m)^(version = )"[^"]+"'),
}

UV_LOCK = "uv.lock"
UV_LOCK_RE = re.compile(r'(?m)^(name = "mech-agent"\nversion = )"([^"]+)"')


class BumpError(Exception):
    pass


def _read_versions(root: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for rel, pattern in _PATTERNS.items():
        path = root / rel
        if not path.is_file():
            raise BumpError(f"{rel}: file not found")
        match = pattern.search(path.read_text(encoding="utf-8"))
        if match is None:
            raise BumpError(f"{rel}: version field not found")
        versions[rel] = match.group(1).strip()
    return versions


def _parse(version: str) -> tuple[int, int, int]:
    match = SEMVER_RE.match(version)
    if match is None:
        raise BumpError(f"not semver: {version}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _write_version(root: Path, version: str) -> None:
    for rel, pattern in _SETTERS.items():
        path = root / rel
        text = path.read_text(encoding="utf-8")
        if rel.endswith(".json"):
            new = pattern.sub(rf"\g<1>{version}\g<2>", text, count=1)
        else:
            new = pattern.sub(rf'\g<1>"{version}"', text, count=1)
        if new == text:
            raise BumpError(f"{rel}: no replacement made")
        path.write_text(new, encoding="utf-8")
    lock = root / UV_LOCK
    if lock.is_file():
        text = lock.read_text(encoding="utf-8")
        new = UV_LOCK_RE.sub(rf'\g<1>"{version}"', text, count=1)
        if new != text:
            lock.write_text(new, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bump", choices=["patch", "minor", "major"])
    group.add_argument("--set", metavar="VERSION")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    try:
        versions = _read_versions(root)
        unique = set(versions.values())
        if len(unique) != 1:
            raise BumpError(f"version files disagree: {versions}")
        current = next(iter(unique))
        major, minor, patch = _parse(current)
        if args.set:
            target = args.set.removeprefix("v")
            _parse(target)
        elif args.bump == "major":
            target = f"{major + 1}.0.0"
        elif args.bump == "minor":
            target = f"{major}.{minor + 1}.0"
        else:
            target = f"{major}.{minor}.{patch + 1}"
        _write_version(root, target)
    except BumpError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
