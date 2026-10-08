"""Design report assembly: JSON contract plus a human-readable summary."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any, cast

from .brief import DesignBrief
from .gates import GateReport
from .generators.common import GeneratedDesign, shape_bbox


def build_report(
    brief: DesignBrief,
    design: GeneratedDesign,
    gate_report: GateReport,
) -> dict[str, Any]:
    parts: list[dict[str, Any]] = []
    for part in design.parts:
        box = shape_bbox(part.shape)
        parts.append(
            {
                "part_id": part.part_id,
                "volume_mm3": round(float(part.shape.volume), 3),
                "bbox_mm": [round(v, 3) for v in box.size],
            }
        )
    report = gate_report.to_dict(brief)
    report["schema_version"] = 1
    report["parts"] = parts
    report["references"] = [r.reference_id for r in design.references]
    report["provenance"] = design.provenance
    return report


VISION_RECORD_WITH = "mech_record_vision_review"


def _vision_checklist(entry: dict[str, Any], design_name: str) -> str:
    """Best-effort checklist slug for one renders entry."""
    kind = entry.get("kind")
    if kind == "dxf":
        return "dxf_outline"
    if kind == "views":
        # `<name>.step` renders the assembly sheet; `<name>-<part>.step` a part.
        source = Path(str(entry.get("source", ""))).name
        return "assembly_render" if source == f"{design_name}.step" else "part_render"
    return "intake_image"


def vision_points(renders: list[dict[str, Any]], design_name: str) -> list[dict[str, str]]:
    """Vision-review packet for the renders the report already lists."""
    return [
        {
            "image_path": str(entry["png_path"]),
            "checklist": _vision_checklist(entry, design_name),
            "record_with": VISION_RECORD_WITH,
        }
        for entry in renders
        if entry.get("png_path")
    ]


def write_report(
    brief: DesignBrief,
    design: GeneratedDesign,
    gate_report: GateReport,
    out_dir: Path,
    *,
    renders: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> Path:
    report = build_report(brief, design, gate_report)
    if renders is not None:
        # L2 advisory: renders never alter the verdict, they are listed so
        # the review step knows which images need a vision review.
        report["renders"] = (
            {"status": "ok", "files": renders} if isinstance(renders, list) else renders
        )
        if isinstance(renders, list):
            report["vision_points"] = vision_points(renders, brief.name)
    lints: dict[str, Any] = {}
    for lint_path in sorted(out_dir.glob("*.dxf_lint.json")):
        with contextlib.suppress(json.JSONDecodeError):
            lints[lint_path.name] = json.loads(lint_path.read_text(encoding="utf-8"))
    if lints:
        report["advisories"] = {"dxf_lint": lints}
    path = out_dir / "design-report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = out_dir / "design-report.md"
    md.write_text(render_markdown(report), encoding="utf-8")
    return path


def render_markdown(report: dict[str, Any]) -> str:
    design = report["design"]
    lines = [
        f"# Design report: {design['name']}",
        "",
        f"- type: {design['design_type']} / material: {design['material']} / "
        f"process: {design['process']}",
        f"- brief sha256: `{design['brief_sha256']}`",
        f"- verdict: **{report['verdict']}** "
        f"(pass {report['summary']['pass']}, fail {report['summary']['fail']}, "
        f"unknown {report['summary']['unknown']})",
        "",
        "## Parts",
        "",
        "| part | volume (mm3) | bbox (mm) |",
        "| --- | --- | --- |",
    ]
    for part in report["parts"]:
        bbox = " x ".join(str(v) for v in part["bbox_mm"])
        lines.append(f"| {part['part_id']} | {part['volume_mm3']} | {bbox} |")
    lines += [
        "",
        "## Checks",
        "",
        "| check | subject | status | measured | limit | detail |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        measured = "" if check["measured"] is None else check["measured"]
        limit = "" if check["limit"] is None else check["limit"]
        lines.append(
            f"| {check['id']} | {check['subject']} | {check['status']} "
            f"| {measured} | {limit} | {check['detail']} |"
        )
    renders: Any = report.get("renders")
    if renders is not None:
        lines += ["", "## Renders (advisory — review each)", ""]
        renders_ok = (
            isinstance(renders, dict) and cast(dict[str, Any], renders).get("status") == "ok"
        )
        if renders_ok:
            files = cast(list[dict[str, Any]], cast(dict[str, Any], renders).get("files") or [])
            for entry in files:
                lines.append(f"- {entry['kind']}: `{entry['png_path']}` (from `{entry['source']}`)")
        else:
            detail = (
                cast(dict[str, Any], renders).get("detail", "unknown")
                if isinstance(renders, dict)
                else renders
            )
            lines.append(f"- render error: {detail}")
    lints = report.get("advisories", {}).get("dxf_lint", {})
    if lints:
        lines += [
            "",
            "## DXF lint (advisory)",
            "",
        ]
        for name, lint in lints.items():
            lines.append(
                f"- {name}: {lint['verdict']} "
                f"({lint['errors']} errors, {lint['warnings']} warnings)"
            )
            for finding in lint["findings"]:
                lines.append(
                    f"  - {finding['severity']}: {finding['type']} — {finding['description']}"
                )
    lines.append("")
    return "\n".join(lines)
