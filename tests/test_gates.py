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


def _with_anchor(brief: DesignBrief, position: list[float] | None) -> DesignBrief:
    data = brief.model_dump(mode="json")
    anchor: dict[str, Any] = {"name": "clip-01", "kind": "clip"}
    if position is not None:
        anchor["position_mm"] = position
    data["harness_anchors"] = [anchor]
    return DesignBrief.model_validate(data)


def test_harness_anchor_within_envelope(enclosure_brief: DesignBrief, tmp_path: Path):
    """Anchors measured from the assembly bbox min corner pass inside it."""
    brief = _with_anchor(enclosure_brief, [60.0, 0.0, 20.0])
    out_dir = tmp_path / "out"
    design = _authored(brief, out_dir)
    report = run_gates(brief, design, out_dir)
    checks = [c for c in report.checks if c.id == "harness_anchor.within_envelope"]
    assert len(checks) == 1
    assert checks[0].status == "pass"
    assert checks[0].subject == "clip-01"
    assert report.verdict == "pass"


def test_harness_anchor_outside_envelope_fails(enclosure_brief: DesignBrief, tmp_path: Path):
    brief = _with_anchor(enclosure_brief, [200.0, 0.0, 20.0])
    out_dir = tmp_path / "out"
    design = _authored(brief, out_dir)
    report = run_gates(brief, design, out_dir)
    checks = [c for c in report.checks if c.id == "harness_anchor.within_envelope"]
    assert checks[0].status == "fail"
    assert report.verdict == "fail"


def test_harness_anchor_without_position_no_check(enclosure_brief: DesignBrief, tmp_path: Path):
    brief = _with_anchor(enclosure_brief, None)
    out_dir = tmp_path / "out"
    design = _authored(brief, out_dir)
    report = run_gates(brief, design, out_dir)
    assert not [c for c in report.checks if c.id == "harness_anchor.within_envelope"]
