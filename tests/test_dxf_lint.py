"""DXF lint tests — advisory readability checks on exported drawings."""

# ezdxf's annotations are only partially typed.
# pyright: reportPrivateImportUsage=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import io
import json
from pathlib import Path

import ezdxf
import pytest

from mech.brief import DesignBrief
from mech.dxf_lint import DxfLintError, DxfLintReport, lint_file, lint_text
from mech.export import export_design
from mech.gates import run_gates
from mech.generators import generate
from mech.report import write_report


def _dxf(outline: bool = True) -> str:
    doc = ezdxf.new()
    if outline:
        doc.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": "0"})
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue()


def test_exported_dxf_lints_clean(enclosure_brief: DesignBrief, tmp_path: Path):
    out_dir = tmp_path / "out"
    design = generate(enclosure_brief)
    export_design(enclosure_brief, design, out_dir)
    for lint_path in sorted(out_dir.glob("*.dxf_lint.json")):
        report = DxfLintReport.model_validate_json(lint_path.read_text(encoding="utf-8"))
        assert report.verdict == "pass", report.findings
        assert report.errors == 0
    assert (out_dir / "demo-shell.dxf_lint.json").is_file()
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "demo-shell.dxf_lint.json" in {f["path"] for f in manifest["files"]}


def test_parse_error_fails_closed(tmp_path: Path):
    bad = tmp_path / "bad.dxf"
    bad.write_text("not a dxf file at all", encoding="utf-8")
    report = lint_file(bad)
    assert report.verdict == "fail"
    assert report.findings[0].type == "parse_error"
    with pytest.raises(DxfLintError):
        lint_text("not a dxf file at all", source=bad)


def test_empty_outline_is_an_error():
    report = lint_text(_dxf(outline=False), source=Path("empty.dxf"))
    assert report.verdict == "fail"
    assert any(f.type == "empty_outline" for f in report.findings)


def test_unannotated_dxf_warns_about_missing_furniture():
    report = lint_text(_dxf(), source=Path("raw.dxf"))
    assert report.verdict == "pass"  # warnings never flip the verdict
    types = {f.type for f in report.findings}
    assert {"missing_frame", "missing_title", "missing_dimensions", "missing_notes"} <= types


def test_dxf_with_holes_but_no_table_warns():
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True, dxfattribs={"layer": "0"})
    msp.add_circle((5, 5), 2.0, dxfattribs={"layer": "0"})
    stream = io.StringIO()
    doc.write(stream)
    report = lint_text(stream.getvalue(), source=Path("holes.dxf"))
    assert report.verdict == "pass"
    types = {f.type for f in report.findings}
    assert "hole_table_missing" in types
    assert "missing_notes" in types


def test_annotated_dxf_carries_notes_hole_table_and_fits(
    enclosure_brief: DesignBrief, tmp_path: Path
):
    out_dir = tmp_path / "out"
    design = generate(enclosure_brief)
    export_design(enclosure_brief, design, out_dir)
    dxf_path = out_dir / "demo-lid.dxf"
    assert dxf_path.is_file()
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    texts: dict[str, list[str]] = {}
    for e in msp:
        if e.dxftype() == "TEXT":
            texts.setdefault(e.dxf.layer, []).append(e.dxf.text)
    title = " ".join(texts.get("TITLE", []))
    assert "MATERIAL ABS" in title
    assert "PROCESS  fdm" in title
    notes = " ".join(texts.get("NOTES", []))
    assert "HOLE TABLE" in notes
    assert "GEN TOL" in notes
    assert "LOWER-LEFT" in notes
    assert "FIT FT1" in notes and "H7/g6" in notes
    # Every hole in the outline has a table row and an on-drawing tag.
    from mech.dxf_annotate import hole_circles

    holes = hole_circles(msp)
    tag_rows = [t for t in texts.get("NOTES", []) if t.startswith("A")]
    assert len(holes) == len(tag_rows) > 0
    dims = texts.get("DIMS", [])
    for i in range(len(holes)):
        assert f"A{i + 1}" in dims
    # The drawing still lints clean.
    report = lint_text(dxf_path.read_text(encoding="utf-8", errors="replace"), source=dxf_path)
    assert report.verdict == "pass", report.findings


def test_design_report_embeds_lint_advisory(enclosure_brief: DesignBrief, tmp_path: Path):
    out_dir = tmp_path / "out"
    design = generate(enclosure_brief)
    export_design(enclosure_brief, design, out_dir)
    gate_report = run_gates(enclosure_brief, design, out_dir)
    write_report(enclosure_brief, design, gate_report, out_dir)
    report = json.loads((out_dir / "design-report.json").read_text(encoding="utf-8"))
    lints = report["advisories"]["dxf_lint"]
    assert lints["demo-shell.dxf_lint.json"]["verdict"] == "pass"
    md = (out_dir / "design-report.md").read_text(encoding="utf-8")
    assert "## DXF lint (advisory)" in md
