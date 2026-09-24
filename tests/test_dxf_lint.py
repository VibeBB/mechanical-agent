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


def _wide_enclosure_brief() -> DesignBrief:
    """A wide, shallow enclosure — the aspect ratio that used to push the
    documentation column outside the frame."""
    return DesignBrief.model_validate(
        {
            "name": "widecase",
            "design_type": "enclosure",
            "material": "ABS",
            "process": "fdm",
            "enclosure": {
                "width_mm": 400,
                "depth_mm": 60,
                "height_mm": 50,
                "wall_mm": 2.0,
                "floor_mm": 2.0,
                "lid": "screw",
                "corner_radius_mm": 4.0,
                "clearance_mm": 0.5,
                "standoff_height_mm": 8.0,
                "board": {
                    "width_mm": 120,
                    "depth_mm": 40,
                    "mount_holes": [
                        {"id": "MH1", "x_mm": -50, "y_mm": -15, "diameter_mm": 3.2},
                        {"id": "MH2", "x_mm": 50, "y_mm": -15, "diameter_mm": 3.2},
                        {"id": "MH3", "x_mm": -50, "y_mm": 15, "diameter_mm": 3.2},
                        {"id": "MH4", "x_mm": 50, "y_mm": 15, "diameter_mm": 3.2},
                    ],
                },
                "openings": [
                    {
                        "id": "O1",
                        "face": "front",
                        "kind": "rect",
                        "width_mm": 20,
                        "height_mm": 8,
                        "center_x_mm": -150,
                    },
                    {
                        "id": "O2",
                        "face": "front",
                        "kind": "rect",
                        "width_mm": 20,
                        "height_mm": 8,
                        "center_x_mm": -100,
                    },
                    {
                        "id": "O3",
                        "face": "top",
                        "kind": "round",
                        "width_mm": 12,
                        "height_mm": 12,
                        "center_x_mm": 100,
                    },
                ],
                "vent": {
                    "face": "top",
                    "slot_width_mm": 4.0,
                    "slot_length_mm": 30.0,
                    "slot_pitch_mm": 10.0,
                    "margin_mm": 20.0,
                },
                "screw": {"size": "M4", "boss_diameter_mm": 9.0},
            },
        }
    )


def _layer_texts(dxf_path: Path) -> dict[str, list[str]]:
    doc = ezdxf.readfile(str(dxf_path))
    texts: dict[str, list[str]] = {}
    for entity in doc.modelspace():
        if entity.dxftype() == "TEXT":
            texts.setdefault(entity.dxf.layer, []).append(entity.dxf.text)
    return texts


def test_wide_part_documentation_column_stays_inside_frame(tmp_path: Path):
    brief = _wide_enclosure_brief()
    out_dir = tmp_path / "out"
    export_design(brief, generate(brief), out_dir)
    for dxf_path in sorted(out_dir.glob("*.dxf")):
        report = lint_text(dxf_path.read_text(encoding="utf-8", errors="replace"), source=dxf_path)
        assert report.verdict == "pass", report.findings
        assert report.warnings == 0, [
            f.description for f in report.findings if f.severity == "warning"
        ]


def test_contract_tables_land_on_the_part_that_owns_them(tmp_path: Path):
    brief = _wide_enclosure_brief()
    out_dir = tmp_path / "out"
    export_design(brief, generate(brief), out_dir)
    shell = _layer_texts(out_dir / "widecase-shell.dxf")
    lid = _layer_texts(out_dir / "widecase-lid.dxf")
    shell_notes = " ".join(shell.get("NOTES", []))
    lid_notes = " ".join(lid.get("NOTES", []))
    # Front-face openings are cut in the shell; the top vent and round top
    # opening are cut in the lid.
    assert "OPENINGS TABLE" in shell_notes
    assert "O1" in shell_notes and "O2" in shell_notes
    assert "O3" not in shell_notes
    assert "O3" in lid_notes
    assert "VENT top" in lid_notes
    assert "VENT" not in shell_notes
    # Board standoffs belong to the shell.
    assert "BOARD MOUNT TABLE" in shell_notes
    assert "MH1" in shell_notes
    assert "BOARD MOUNT" not in lid_notes
    # Title blocks carry the revision row.
    assert "REV     A" in " ".join(shell.get("TITLE", []))


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
