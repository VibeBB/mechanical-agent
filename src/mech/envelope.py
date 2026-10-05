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
from typing import Any

from .brief import DesignBrief
from .records import sha256_file


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


def _validate_decision_refs(decision_refs: list[str], brief_path: Path | None) -> list[str]:
    """Each ref must be an event_id line in observations/mech/decisions.jsonl."""
    if not decision_refs:
        return []
    from .records import RECORDS_DIR, event_ids
    from .workspace import workspace_root

    log = workspace_root() / RECORDS_DIR / "decisions.jsonl"
    known = event_ids(log)
    missing = [ref for ref in decision_refs if ref not in known]
    if missing:
        raise ValueError(f"decision_ref not found in {log.name}: {', '.join(missing)}")
    return list(decision_refs)


def write_envelope(
    brief: DesignBrief,
    out_path: Path,
    *,
    brief_path: Path | None = None,
    design_report_path: Path | None = None,
    decision_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Write `<name>.envelope.json` plus a `<name>.envelope.provenance.json` sidecar.

    The envelope schema is wire-agent's strict contract and stays
    unchanged; provenance (hashes of the brief, design report and the
    envelope itself, plus VRP decision refs) lives in the sidecar so the
    wire importer is unaffected. Returns the sidecar payload.
    """
    payload = envelope_source(brief)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path = design_report_path
    if report_path is None:
        candidate = out_path.parent / "design-report.json"
        report_path = candidate if candidate.is_file() else None
    provenance: dict[str, Any] = {
        "schema_version": 1,
        "system": "mech",
        "envelope_sha256": sha256_file(out_path),
    }
    if brief_path is not None:
        provenance["brief_path"] = str(brief_path)
        provenance["brief_sha256"] = sha256_file(brief_path)
    if report_path is not None:
        provenance["design_report_sha256"] = sha256_file(report_path)
    # Anchor frame provenance: harness_anchor position_mm values are
    # declared relative to the assembly bbox minimum corner. When the
    # assembly STEP (<brief name>.step, written by author/export into the
    # same out dir) is available, record the frame plus the STEP-space
    # offset so consumers (wire, the render-views overlay) can map anchor
    # -> STEP coordinates as anchor + offset. Regenerating the design here
    # would be far costlier than reading the artifact that was just
    # exported; the file is the cheaper deterministic route.
    assembly_step = out_path.parent / f"{brief.name}.step"
    if assembly_step.is_file():
        try:
            from build123d import import_step  # pyright: ignore[reportUnknownVariableType]

            bbox = import_step(assembly_step).bounding_box()  # pyright: ignore[reportUnknownVariableType]
            provenance["anchor_frame"] = "assembly-bbox-min-corner"
            provenance["step_frame_offset_mm"] = [
                round(float(v), 4) for v in (bbox.min.X, bbox.min.Y, bbox.min.Z)
            ]
        except Exception as exc:
            raise ValueError(f"cannot read assembly STEP {assembly_step}: {exc}") from exc
    refs = _validate_decision_refs(list(decision_refs or []), brief_path)
    if refs:
        provenance["decision_refs"] = refs
    sidecar = out_path.with_suffix(".provenance.json")
    sidecar.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return provenance
