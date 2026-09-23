from __future__ import annotations

from pathlib import Path
from typing import Any

from mech.brief import DesignBrief
from mech.export import export_design
from mech.gates import run_gates
from mech.generators import generate


def _authored(brief: DesignBrief, out_dir: Path):
    design = generate(brief)
    export_design(brief, design, out_dir)
    return design


def test_enclosure_gates_pass(enclosure_brief: DesignBrief, tmp_path: Path):
    out_dir = tmp_path / "out"
    design = _authored(enclosure_brief, out_dir)
    report = run_gates(enclosure_brief, design, out_dir)
    assert report.verdict == "pass"
    assert all(c.status != "fail" for c in report.checks)


def test_gate_report_to_dict(enclosure_brief: DesignBrief, tmp_path: Path):
    out_dir = tmp_path / "out"
    design = _authored(enclosure_brief, out_dir)
    report = run_gates(enclosure_brief, design, out_dir)
    data = report.to_dict(enclosure_brief)
    assert data["verdict"] == "pass"
    assert data["design"]["brief_sha256"]
    checks: list[dict[str, Any]] = list(data["checks"])
    assert all("status" in c for c in checks)


def test_missing_artifacts_fail_closed(enclosure_brief: DesignBrief, tmp_path: Path):
    """Gates without exported artifacts must not pass."""
    out_dir = tmp_path / "out"
    design = generate(enclosure_brief)
    report = run_gates(enclosure_brief, design, out_dir)
    assert report.verdict == "fail"
    assert any(c.status != "pass" for c in report.checks)


def test_corrupted_artifact_fails(enclosure_brief: DesignBrief, tmp_path: Path):
    """Negative test: a truncated STEP file must fail the reload gate."""
    out_dir = tmp_path / "out"
    design = _authored(enclosure_brief, out_dir)
    step = next(out_dir.glob("*.step"))
    data = step.read_bytes()
    step.write_bytes(data[: len(data) // 2])
    report = run_gates(enclosure_brief, design, out_dir)
    assert report.verdict == "fail"


def test_corrupted_mesh_fails(enclosure_brief: DesignBrief, tmp_path: Path):
    """Negative test: overwriting the 3mf with garbage must fail."""
    out_dir = tmp_path / "out"
    design = _authored(enclosure_brief, out_dir)
    mesh = next(out_dir.glob("*.3mf"))
    mesh.write_bytes(b"not a 3mf archive")
    report = run_gates(enclosure_brief, design, out_dir)
    assert report.verdict == "fail"


def test_bracket_gates(bracket_brief_dict: dict[str, Any], tmp_path: Path):
    brief = DesignBrief.model_validate(bracket_brief_dict)
    out_dir = tmp_path / "out"
    design = _authored(brief, out_dir)
    report = run_gates(brief, design, out_dir)
    assert report.verdict == "pass"


def test_gear_gates(gear_brief_dict: dict[str, Any], tmp_path: Path):
    brief = DesignBrief.model_validate(gear_brief_dict)
    out_dir = tmp_path / "out"
    design = _authored(brief, out_dir)
    report = run_gates(brief, design, out_dir)
    assert report.verdict == "pass"
