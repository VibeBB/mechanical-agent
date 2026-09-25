"""mech command line interface.

Subcommands:
  doctor          probe the CAD/tool environment (JSON verdict)
  intake          validate an intake.json against a brief.json (JSON verdict)
  author          generate parts, export artifacts, run all gates, write the report
  export          generate parts and export artifacts without gates
  gates           regenerate the design and re-run all gates on existing artifacts
  render          rasterize an exported DXF to PNG for the advisory vision lane
  export-envelope emit the wire-agent EnvelopeSource contract (ADR-0003)

All commands print a JSON verdict to stdout; the verdict is fail-closed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from .brief import DesignBrief, load_brief
from .doctor import run_doctor
from .export import export_design
from .gates import run_gates
from .generators import generate
from .intake import check_intake
from .report import write_report


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("verdict") in ("pass", "ready") else 1


def _cmd_doctor(_args: argparse.Namespace) -> dict[str, Any]:
    return run_doctor()


def _emit_doctor(args: argparse.Namespace) -> int:
    payload = run_doctor()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if args.warn or payload.get("verdict") in ("pass", "ready") else 1


def _cmd_export_envelope(args: argparse.Namespace) -> dict[str, Any]:
    from .envelope import write_envelope

    out_path = Path(args.out)
    try:
        brief = load_brief(Path(args.brief))
        write_envelope(brief, out_path)
    except Exception as exc:
        return {"verdict": "fail", "stage": "export-envelope", "detail": str(exc)}
    return {
        "verdict": "pass",
        "design": brief.name,
        "anchors": [anchor.name for anchor in brief.harness_anchors],
        "out": str(out_path),
    }


def _cmd_intake(args: argparse.Namespace) -> dict[str, Any]:
    from .intake import load_intake

    brief = load_brief(Path(args.brief))
    intake = load_intake(Path(args.intake))
    report = check_intake(brief, intake, Path(args.brief), Path(args.intake))
    return report.model_dump(mode="json")


def _load_and_generate(brief_path: str) -> tuple[DesignBrief, Any]:
    brief = load_brief(Path(brief_path))
    design = generate(brief)
    return brief, design


def _cmd_author(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.out)
    try:
        brief, design = _load_and_generate(args.brief)
    except Exception as exc:
        return {"verdict": "fail", "stage": "generate", "detail": str(exc)}
    export_design(brief, design, out_dir)
    gate_report = run_gates(brief, design, out_dir)
    report_path = write_report(brief, design, gate_report, out_dir)
    result = gate_report.to_dict(brief)
    result["report_path"] = str(report_path)
    return result


def _cmd_export(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.out)
    try:
        brief, design = _load_and_generate(args.brief)
    except Exception as exc:
        return {"verdict": "fail", "stage": "generate", "detail": str(exc)}
    manifest = export_design(brief, design, out_dir)
    return {
        "verdict": "pass",
        "design": brief.name,
        "files": [entry["path"] for entry in manifest["files"]],
    }


def _cmd_dxf_lint(args: argparse.Namespace) -> dict[str, Any]:
    from .dxf_lint import lint_file

    report = lint_file(
        Path(args.drawing),
        Path(args.out) if args.out else None,
    )
    return report.model_dump(mode="json")


def _cmd_render(args: argparse.Namespace) -> dict[str, Any]:
    from .render import render_dxf

    result = render_dxf(
        Path(args.dxf),
        Path(args.out) if args.out else None,
        dpi=args.dpi,
        baseline_path=Path(args.baseline) if args.baseline else None,
    )
    payload: dict[str, Any] = {
        "verdict": "pass",
        "dxf_path": result.dxf_path,
        "svg_path": result.svg_path,
        "png_path": result.png_path,
        "image_sha256": result.image_sha256,
    }
    if result.baseline is not None:
        payload["baseline"] = result.baseline
        payload["baseline_sha256"] = result.baseline_sha256
    return payload


def _cmd_gates(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.out)
    try:
        brief, design = _load_and_generate(args.brief)
    except Exception as exc:
        return {"verdict": "fail", "stage": "generate", "detail": str(exc)}
    gate_report = run_gates(brief, design, out_dir)
    report_path = write_report(brief, design, gate_report, out_dir)
    result = gate_report.to_dict(brief)
    result["report_path"] = str(report_path)
    return result


def _cmd_review_record(args: argparse.Namespace) -> dict[str, Any]:
    """Write `review-visual-<slug>.advisory.json` for a reviewed image.

    The reviewer supplies impression/findings as JSON; this command binds
    them to the image bytes (sha256), validates the detail against the
    typed schema, and writes the record deterministically — instead of a
    hand-assembled JSON that could drift from `advisory.py`.
    """
    from .advisory import write_review_record

    image = Path(args.image)
    try:
        raw: Any = json.loads(Path(args.findings).read_text(encoding="utf-8"))
        raw_list = cast(list[Any], raw) if isinstance(raw, list) else None
        if raw_list is None or not all(isinstance(item, dict) for item in raw_list):
            raise ValueError("findings JSON must be a list of objects")
        findings = cast(list[dict[str, Any]], raw_list)
        impression = (
            Path(args.impression_file).read_text(encoding="utf-8").strip()
            if args.impression_file
            else (args.impression or "").strip()
        )
        path = write_review_record(
            image,
            model=args.model,
            checklist=args.checklist,
            impression=impression,
            findings=findings,
            summary=args.summary or "",
            out_dir=Path(args.out) if args.out else None,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"verdict": "fail", "stage": "review-record", "detail": str(exc)}
    return {"verdict": "pass", "record": str(path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mech",
        description="Deterministic mechanical-design pipeline (OpenHands plugin core)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_p = sub.add_parser("doctor", help="probe the environment")
    doctor_p.add_argument(
        "--warn",
        action="store_true",
        help="print the verdict but always exit 0 (advisory mode for hooks)",
    )

    intake_p = sub.add_parser("intake", help="validate intake.json against a brief")
    intake_p.add_argument("--brief", required=True)
    intake_p.add_argument("--intake", required=True)

    author_p = sub.add_parser("author", help="generate + export + gates + report")
    author_p.add_argument("--brief", required=True)
    author_p.add_argument("--out", required=True)

    export_p = sub.add_parser("export", help="generate + export only")
    export_p.add_argument("--brief", required=True)
    export_p.add_argument("--out", required=True)

    gates_p = sub.add_parser("gates", help="re-run gates on an output directory")
    gates_p.add_argument("--brief", required=True)
    gates_p.add_argument("--out", required=True)

    lint_p = sub.add_parser(
        "dxf-lint",
        help="advisory readability lint for a DXF drawing (never a gate verdict)",
    )
    lint_p.add_argument("--in", dest="drawing", required=True, help="DXF drawing to lint")
    lint_p.add_argument("--out", default=None, help="optional report output path")

    render_p = sub.add_parser(
        "render",
        help="rasterize an exported DXF to PNG for the advisory vision lane",
    )
    render_p.add_argument("--dxf", required=True, help="DXF drawing to render")
    render_p.add_argument("--out", default=None, help="output PNG path (default: <dxf>.png)")
    render_p.add_argument("--dpi", type=int, default=200, help="raster resolution")
    render_p.add_argument(
        "--baseline",
        default=None,
        help="optional baseline JSON: recorded when missing, compared when present",
    )

    envelope_p = sub.add_parser(
        "export-envelope",
        help="emit the wire-agent envelope contract",
    )
    envelope_p.add_argument("--brief", required=True)
    envelope_p.add_argument("--out", required=True)

    review_p = sub.add_parser(
        "review-record",
        help="write a validated review-visual-<slug>.advisory.json for an image",
    )
    review_p.add_argument("--image", required=True, help="the image the review read")
    review_p.add_argument("--model", required=True, help="reviewer model name")
    review_p.add_argument(
        "--checklist",
        required=True,
        choices=["dxf_outline", "part_render", "intake_image"],
    )
    review_p.add_argument("--summary", default=None)
    review_p.add_argument("--out", default=None)
    review_p.add_argument("--impression", default=None, help="subjective reading (required)")
    review_p.add_argument(
        "--impression-file",
        default=None,
        help="text file with the subjective reading (alternative to --impression)",
    )
    review_p.add_argument(
        "--findings",
        required=True,
        help="JSON file: list of {category, severity, note, bbox?}",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return _emit_doctor(args)
    handlers = {
        "doctor": _cmd_doctor,
        "export-envelope": _cmd_export_envelope,
        "intake": _cmd_intake,
        "author": _cmd_author,
        "export": _cmd_export,
        "gates": _cmd_gates,
        "dxf-lint": _cmd_dxf_lint,
        "render": _cmd_render,
        "review-record": _cmd_review_record,
    }
    handler = handlers[args.command]
    try:
        payload = handler(args)
    except Exception as exc:  # fail-closed: never crash without a verdict
        payload = {"verdict": "fail", "stage": args.command, "detail": str(exc)}
    return _emit(payload)


if __name__ == "__main__":
    sys.exit(main())
