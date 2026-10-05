#!/usr/bin/env python3
"""SessionStart hook: surface unanswered UX-creator liaison requests.

Lists ``liaison/*.ux-request.json`` in the workspace whose
``target_agent`` is ``mech`` and that have no sibling
``<id>.ux-response.json``, and prints them as additional context telling
the agent to call ``mech_ux_inbox`` and answer each. Silent (exit 0, no
output) when there is nothing pending or the liaison directory does not
exist. Stdlib only; hook errors never block a session.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, cast


def _project_dir(payload: dict[str, Any]) -> Path:
    return Path(
        os.environ.get("OPENHANDS_PROJECT_DIR") or payload.get("working_dir") or "."
    ).resolve()


def _pending(root: Path) -> list[str]:
    directory = root / "liaison"
    if not directory.is_dir():
        return []
    pending: list[str] = []
    for path in sorted(directory.glob("*.ux-request.json")):
        try:
            value: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict):
            continue
        request = cast(dict[str, Any], value)
        if request.get("target_agent") != "mech":
            continue
        request_id = str(request.get("id") or path.stem.removesuffix(".ux-request"))
        if not (directory / f"{request_id}.ux-response.json").is_file():
            pending.append(str(request_id))
    return pending


def main() -> int:
    try:
        payload: Any = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    pending = _pending(_project_dir(cast(dict[str, Any], payload)))
    if not pending:
        return 0
    lines = "\n".join(f"- liaison/{rid}.ux-request.json" for rid in pending)
    context = (
        "UX-creator liaison requests are waiting for mech:\n"
        f"{lines}\n"
        "Call mech_ux_inbox for the full state and answer every request with "
        "mech_ux_respond (accepted/in_progress early; done only with passing "
        "gate verdicts plus decision_refs and impression_refs)."
    )
    print(json.dumps({"decision": "allow", "additionalContext": context}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
