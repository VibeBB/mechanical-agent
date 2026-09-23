#!/usr/bin/env python3
"""Deterministic authoring entry point.

``python scripts/e2e_authoring.py --brief design.brief.json --out out/x``
runs the whole pipeline: brief validation -> generate -> export -> gates ->
design report, then prints the gate verdict JSON on stdout. Exit code is 0
only when every gate passes; any failure is fail-closed (exit 2).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="design brief JSON path")
    parser.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args(argv)

    from mech.brief import load_brief
    from mech.export import export_design
    from mech.gates import run_gates
    from mech.generators import generate
    from mech.report import write_report

    out_dir = Path(args.out)
    try:
        brief = load_brief(Path(args.brief))
    except Exception as exc:
        print(
            json.dumps(
                {"verdict": "fail", "stage": "brief", "detail": str(exc)},
                indent=2,
            )
        )
        return 2

    try:
        design = generate(brief)
    except Exception as exc:
        print(
            json.dumps(
                {"verdict": "fail", "stage": "generate", "detail": str(exc)},
                indent=2,
            )
        )
        return 2

    export_design(brief, design, out_dir)
    report = run_gates(brief, design, out_dir)
    report_path = write_report(brief, design, report, out_dir)
    payload = report.to_dict(brief)
    payload["report_path"] = str(report_path)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if report.verdict == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
