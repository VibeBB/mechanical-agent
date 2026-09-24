"""mech command line interface.

Subcommands:
  doctor          probe the CAD/tool environment (JSON verdict)
  intake          validate an intake.json against a brief.json (JSON verdict)
  author          generate parts, export artifacts, run all gates, write the report
  export          generate parts and export artifacts without gates
  gates           regenerate the design and re-run all gates on existing artifacts
  export-envelope emit the wire-agent EnvelopeSource contract (ADR-0003)

All commands print a JSON verdict to stdout; the verdict is fail-closed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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

    envelope_p = sub.add_parser(
        "export-envelope",
        help="emit the wire-agent envelope contract",
    )
    envelope_p.add_argument("--brief", required=True)
    envelope_p.add_argument("--out", required=True)

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
    }
    handler = handlers[args.command]
    try:
        payload = handler(args)
    except Exception as exc:  # fail-closed: never crash without a verdict
        payload = {"verdict": "fail", "stage": args.command, "detail": str(exc)}
    return _emit(payload)


if __name__ == "__main__":
    sys.exit(main())
