"""Envelope contract export for wire-agent (ADR-0003).

Projects the brief's `harness_anchors` declarations into the wire-side
`EnvelopeSource` schema:

    {schema_version: 1, system: "mech",
     anchors: [{name, kind, position_mm?}]}

The emitted file is a deterministic projection of the brief; the wire
importer validates it again and records its sha256.
"""

from __future__ import annotations

import json
from pathlib import Path

from .brief import DesignBrief


def envelope_source(brief: DesignBrief) -> dict[str, object]:
    """Return the EnvelopeSource payload for the brief's harness anchors."""
    if not brief.harness_anchors:
        raise ValueError(
            "brief declares no harness_anchors; the envelope contract "
            "needs at least one fixturing point"
        )
    anchors: list[dict[str, object]] = []
    for anchor in brief.harness_anchors:
        entry: dict[str, object] = {"name": anchor.name, "kind": anchor.kind}
        if anchor.position_mm is not None:
            entry["position_mm"] = list(anchor.position_mm)
        anchors.append(entry)
    return {"schema_version": 1, "system": "mech", "anchors": anchors}


def write_envelope(brief: DesignBrief, out_path: Path) -> Path:
    """Write `<name>.envelope.json`-shaped bytes to `out_path`."""
    payload = envelope_source(brief)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path
