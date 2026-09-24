"""Design report assembly: JSON contract plus a human-readable summary."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

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


def write_report(
    brief: DesignBrief,
    design: GeneratedDesign,
    gate_report: GateReport,
    out_dir: Path,
) -> Path:
    report = build_report(brief, design, gate_report)
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
