"""Check the brief against the hash-pinned UX-creator CMF part it realises."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, cast

from .brief import DesignBrief
from .workspace import workspace_path


def resolve_cmf(brief: DesignBrief, base_dir: Path, *, confine: bool = False) -> Path | None:
    """Path of ``appearance.cmf.path``; ``confine`` keeps MCP reads inside the workspace."""
    source = brief.appearance.cmf if brief.appearance is not None else None
    if source is None:
        return None
    if confine:
        return workspace_path(source.path, root=base_dir)
    candidate = Path(source.path)
    return candidate if candidate.is_absolute() else base_dir / candidate


def _by_id(items: object) -> dict[str, dict[str, object]]:
    if not isinstance(items, list):
        return {}
    found: dict[str, dict[str, object]] = {}
    for item in cast(list[object], items):
        if isinstance(item, dict):
            entry = cast(dict[str, object], item)
            if isinstance(entry.get("id"), str):
                found[cast(str, entry["id"])] = entry
    return found


def cmf_problems(
    brief: DesignBrief, path: Path | None
) -> tuple[Literal["pass", "fail", "unknown"], str]:
    """``(status, detail)`` of the ``appearance.cmf`` check."""
    assert brief.appearance is not None and brief.appearance.cmf is not None
    source = brief.appearance.cmf
    if path is None or not path.is_file():
        return "unknown", f"{source.path}: pinned UX contract missing"
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != source.sha256:
        return "fail", f"stale pin: file sha256 {actual} != brief {source.sha256}"
    try:
        payload = cast(object, json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return "fail", f"{source.path}: invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return "fail", f"{source.path}: not a JSON object"
    contract = cast(dict[str, object], payload)
    if contract.get("system") != "ux-creator":
        return "fail", f"{source.path}: not a ux-creator contract"
    cmf = contract.get("cmf")
    if not isinstance(cmf, dict):
        return "fail", f"{source.path}: contract declares no cmf"
    block = cast(dict[str, object], cmf)
    part = _by_id(block.get("parts")).get(source.part)
    if part is None:
        return "fail", f"{source.path}: no cmf part {source.part!r}"
    material = _by_id(block.get("materials")).get(cast(str, part.get("material", "")))
    name = material.get("name") if material is not None else None
    if not isinstance(name, str):
        return "fail", f"cmf part {source.part}: material is not declared"
    if name.strip().upper() != brief.material.strip().upper():
        return "fail", f"cmf part {source.part} is {name}, brief material is {brief.material}"
    return "pass", f"cmf part {source.part}: {name}"
