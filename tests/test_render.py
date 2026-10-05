"""DXF render tests — advisory vision-lane rasterization and visual baselines."""

# ezdxf's annotations are only partially typed.
# pyright: reportPrivateImportUsage=false
# pyright: reportPrivateUsage=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any

import ezdxf
import pytest

from mech.brief import DesignBrief
from mech.export import export_design
from mech.generators import generate
from mech.render import RenderError, render_dxf

_RSVG = shutil.which("rsvg-convert")


def _dxf(tmp_path: Path) -> Path:
    doc = ezdxf.new()
    doc.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": "0"})
    path = tmp_path / "part.dxf"
    doc.saveas(str(path))
    return path


@pytest.mark.skipif(_RSVG is None, reason="rsvg-convert not installed")
def test_render_dxf_produces_png(tmp_path: Path):
    dxf = _dxf(tmp_path)
    result = render_dxf(dxf)
    png = Path(result.png_path)
    assert png.is_file()
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert Path(result.svg_path).is_file()
    assert len(result.image_sha256) == 64


@pytest.mark.skipif(_RSVG is None, reason="rsvg-convert not installed")
def test_render_exported_dxf(enclosure_brief: DesignBrief, tmp_path: Path):
    out_dir = tmp_path / "out"
    design = generate(enclosure_brief)
    export_design(enclosure_brief, design, out_dir)
    dxf = next(out_dir.glob("*.dxf"))
    result = render_dxf(dxf)
    assert Path(result.png_path).is_file()


def test_render_missing_source_fails_closed(tmp_path: Path):
    with pytest.raises(RenderError, match="missing or empty"):
        render_dxf(tmp_path / "nope.dxf")


def test_render_non_dxf_fails_closed(tmp_path: Path):
    bad = tmp_path / "part.step"
    bad.write_text("x", encoding="utf-8")
    with pytest.raises(RenderError, match=r"not a \.dxf"):
        render_dxf(bad)


def test_render_invalid_dxf_fails_closed(tmp_path: Path):
    bad = tmp_path / "bad.dxf"
    bad.write_text("not a dxf file at all", encoding="utf-8")
    with pytest.raises(RenderError, match="cannot read DXF"):
        render_dxf(bad)


def test_render_empty_dxf_fails_closed(tmp_path: Path):
    doc = ezdxf.new()
    path = tmp_path / "empty.dxf"
    doc.saveas(str(path))
    with pytest.raises(RenderError, match="no modelspace entities"):
        render_dxf(path)


@pytest.mark.skipif(_RSVG is None, reason="rsvg-convert not installed")
def test_baseline_record_match_diff(tmp_path: Path):
    dxf = _dxf(tmp_path)
    baseline = tmp_path / "baseline.json"
    first = render_dxf(dxf, baseline_path=baseline)
    assert first.baseline == "recorded"
    assert baseline.is_file()
    second = render_dxf(dxf, baseline_path=baseline)
    assert second.baseline == "match"
    assert second.baseline_sha256 == first.image_sha256
    doc = ezdxf.readfile(dxf)
    doc.modelspace().add_line((0, 0), (50, 0), dxfattribs={"layer": "0"})
    doc.saveas(str(dxf))
    third = render_dxf(dxf, baseline_path=baseline)
    assert third.baseline == "diff"
    assert third.baseline_sha256 == first.image_sha256


@pytest.mark.skipif(_RSVG is None, reason="rsvg-convert not installed")
def test_baseline_corrupt_fails_closed(tmp_path: Path):
    dxf = _dxf(tmp_path)
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{not json", encoding="utf-8")
    with pytest.raises(RenderError, match="cannot read baseline"):
        render_dxf(dxf, baseline_path=baseline)


def test_cli_render(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    if _RSVG is None:
        pytest.skip("rsvg-convert not installed")
    import json

    from mech.cli import main

    dxf = _dxf(tmp_path)
    rc = main(["render", "--dxf", str(dxf)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "pass"
    assert Path(out["png_path"]).is_file()


def test_cli_render_fail_closed(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    import json

    from mech.cli import main

    rc = main(["render", "--dxf", str(tmp_path / "nope.dxf")])
    assert rc != 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "fail"


def test_mcp_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if _RSVG is None:
        pytest.skip("rsvg-convert not installed")
    from mcp import types

    from mech.mcp_server import call_tool

    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    dxf = _dxf(tmp_path)
    result = call_tool("mech_render", {"dxf_path": str(dxf)})
    assert not result.isError
    import json

    text_block = result.content[0]
    assert isinstance(text_block, types.TextContent)
    payload = json.loads(text_block.text)
    assert payload["verdict"] == "pass"
    image_blocks = [c for c in result.content if isinstance(c, types.ImageContent)]
    assert len(image_blocks) == 1
    assert image_blocks[0].mimeType == "image/png"


def test_mcp_render_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from mech.mcp_server import call_tool

    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    result = call_tool("mech_render", {"dxf_path": str(tmp_path / "nope.dxf")})
    assert result.isError


@pytest.mark.skipif(_RSVG is None, reason="rsvg-convert not installed")
def test_render_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MECH_RSVG_CONVERT", "/nonexistent-rsvg")
    with pytest.raises(RenderError, match="not available"):
        render_dxf(_dxf(tmp_path))


def _step(tmp_path: Path, name: str = "part.step") -> Path:
    from build123d import Box
    from build123d.exporters3d import export_step

    path = tmp_path / name
    export_step(Box(40, 30, 20), str(path))
    return path


@pytest.mark.skipif(_RSVG is None, reason="rsvg-convert not installed")
def test_render_views_produces_sheet(tmp_path: Path):
    from mech.views import render_views

    step = _step(tmp_path)
    result = render_views(step)
    png = Path(result.png_path)
    assert png.name == "part.views.png"
    assert png.is_file()
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert Path(result.svg_path).name == "part.views.svg"
    assert result.views == ("front", "top", "right", "isometric")
    assert len(result.image_sha256) == 64
    svg = Path(result.svg_path).read_text(encoding="utf-8")
    for label in ("front", "top", "right", "isometric"):
        assert label in svg
    assert "stroke-dasharray" in svg  # hidden edges drawn
    assert "overall:" in svg  # bbox dimension text


def test_render_views_fail_closed(tmp_path: Path):
    from mech.views import render_views

    with pytest.raises(RenderError, match="missing or empty"):
        render_views(tmp_path / "nope.step")
    bad = tmp_path / "part.dxf"
    bad.write_text("x", encoding="utf-8")
    with pytest.raises(RenderError, match=r"not a \.step"):
        render_views(bad)
    step = tmp_path / "junk.step"
    step.write_bytes(b"not a step file")
    with pytest.raises(RenderError):
        render_views(step)


def test_render_views_symlink_rejected(tmp_path: Path):
    from mech.views import render_views

    real = _step(tmp_path, "real.step")
    link = tmp_path / "link.step"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="symlink"):
        render_views(link)


@pytest.mark.skipif(_RSVG is None, reason="rsvg-convert not installed")
def test_render_views_baseline(tmp_path: Path):
    from mech.views import render_views

    step = _step(tmp_path)
    baseline = tmp_path / "baseline.json"
    first = render_views(step, baseline_path=baseline)
    assert first.baseline == "recorded"
    second = render_views(step, baseline_path=baseline)
    assert second.baseline == "match"
    assert second.baseline_sha256 == first.image_sha256


def _asymmetric_step(tmp_path: Path) -> Path:
    """Box plus a separate small cube at the +X/+Y/+Z corner, as STEP."""
    from build123d import Box, Compound, Pos, export_step

    path = tmp_path / "asym.step"
    export_step(
        Compound(children=[Box(40, 30, 20), Pos(20, 15, 10) * Box(4, 4, 4)]),
        str(path),
    )
    return path


def _path_length(line: list[tuple[float, float]]) -> float:
    return sum(
        math.hypot(line[i + 1][0] - line[i][0], line[i + 1][1] - line[i][1])
        for i in range(len(line) - 1)
    )


def test_view_orientations(tmp_path: Path) -> None:
    """Third-angle axes: the +X/+Y/+Z corner feature lands where expected."""
    from build123d import import_step

    from mech.views import _view_geometry  # pyright: ignore[reportPrivateUsage]

    compound = import_step(_asymmetric_step(tmp_path))
    bounds = compound.bounding_box()
    center = (
        bounds.min.X + bounds.size.X / 2,
        bounds.min.Y + bounds.size.Y / 2,
        bounds.min.Z + bounds.size.Z / 2,
    )

    def marker_center(
        direction: tuple[float, float, float], up: tuple[float, float, float]
    ) -> tuple[float, float]:
        visible, hidden = _view_geometry(compound, center, direction, up)
        # the marker's 4 mm edges are the only short polylines in the sheet
        small = [
            point
            for line in [*visible, *hidden]
            if 0.1 < _path_length(line) < 6.0
            for point in line
        ]
        assert small, "marker edges missing from projection"
        xs = [p[0] for p in small]
        ys = [p[1] for p in small]
        return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2

    # front: screen +x is model +X, screen +y is model +Z
    fx, fy = marker_center((0.0, -1.0, 0.0), (0.0, 0.0, 1.0))
    assert fx > 0 and fy > 0
    # top: screen +x is model +X, screen +y is model +Y
    tx, ty = marker_center((0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
    assert tx > 0 and ty > 0
    # right (viewer at +X, up +Z): screen +x is model +Y, screen +y is +Z
    rx, ry = marker_center((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    assert rx > 0 and ry > 0


def _write_envelope_with_sidecar(
    tmp_path: Path,
    anchors: list[dict[str, Any]],
    offset: list[float],
) -> Path:
    envelope = tmp_path / "demo.envelope.json"
    envelope.write_text(
        json.dumps({"schema_version": 1, "system": "mech", "anchors": anchors}),
        encoding="utf-8",
    )
    tmp_path.joinpath("demo.envelope.provenance.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "system": "mech",
                "anchor_frame": "assembly-bbox-min-corner",
                "step_frame_offset_mm": offset,
            }
        ),
        encoding="utf-8",
    )
    return envelope


def test_envelope_anchors_land_in_assembly_bbox(
    enclosure_brief_dict: dict[str, Any], tmp_path: Path
) -> None:
    """Envelope anchors are declared from the assembly bbox min corner;
    adding the sidecar's step_frame_offset_mm lands them inside the
    exported assembly's STEP bbox."""
    import json as jsonlib

    from build123d import import_step

    data: dict[str, Any] = dict(enclosure_brief_dict)
    data["harness_anchors"] = [
        {"name": "clip-01", "kind": "clip", "position_mm": [60.0, 0.0, 20.0]},
        {"name": "breakout-01", "kind": "breakout", "position_mm": [40.0, 55.0, 10.0]},
    ]
    enclosure_brief = DesignBrief.model_validate(data)
    design = generate(enclosure_brief)
    out_dir = tmp_path / "out"
    export_design(enclosure_brief, design, out_dir)
    assembly = import_step(out_dir / f"{enclosure_brief.name}.step")
    bb = assembly.bounding_box()
    offset = [float(bb.min.X), float(bb.min.Y), float(bb.min.Z)]
    for anchor in enclosure_brief.harness_anchors:
        pos = anchor.position_mm
        assert pos is not None
        step_pt = [pos[i] + offset[i] for i in range(3)]
        assert bb.min.X - 5 <= step_pt[0] <= bb.max.X + 5
        assert bb.min.Y - 5 <= step_pt[1] <= bb.max.Y + 5
        assert bb.min.Z - 5 <= step_pt[2] <= bb.max.Z + 5
    # sidecar round-trip: write_envelope computes the same offset
    from mech.envelope import write_envelope

    provenance = write_envelope(enclosure_brief, out_dir / f"{enclosure_brief.name}.envelope.json")
    assert provenance["anchor_frame"] == "assembly-bbox-min-corner"
    assert provenance["step_frame_offset_mm"] == [round(v, 4) for v in offset]
    assert (
        jsonlib.loads(
            (out_dir / f"{enclosure_brief.name}.envelope.provenance.json").read_text(
                encoding="utf-8"
            )
        )["anchor_frame"]
        == "assembly-bbox-min-corner"
    )


@pytest.mark.skipif(_RSVG is None, reason="rsvg-convert not installed")
def test_render_views_envelope_overlay(tmp_path: Path) -> None:
    from mech.views import render_views

    step = _step(tmp_path)
    envelope = _write_envelope_with_sidecar(
        tmp_path,
        [{"name": "clip-01", "kind": "clip", "position_mm": [20.0, 15.0, 10.0]}],
        [-20.0, -15.0, -10.0],
    )
    result = render_views(step, envelope_path=envelope)
    svg = Path(result.svg_path).read_text(encoding="utf-8")
    assert svg.count("<circle") == 4  # one mark per view
    assert svg.count("clip-01") == 4


def test_render_views_envelope_missing_sidecar_fails_closed(tmp_path: Path) -> None:
    from mech.views import render_views

    step = _step(tmp_path)
    envelope = tmp_path / "demo.envelope.json"
    envelope.write_text('{"schema_version": 1, "system": "mech", "anchors": []}')
    with pytest.raises(RenderError, match="sidecar"):
        render_views(step, envelope_path=envelope)


def test_render_views_envelope_bad_frame_fails_closed(tmp_path: Path) -> None:
    from mech.views import render_views

    step = _step(tmp_path)
    envelope = _write_envelope_with_sidecar(
        tmp_path,
        [{"name": "a", "position_mm": [1.0, 2.0, 3.0]}],
        [0.0, 0.0, 0.0],
    )
    sidecar = tmp_path / "demo.envelope.provenance.json"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["anchor_frame"] = "other-frame"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RenderError, match="anchor_frame"):
        render_views(step, envelope_path=envelope)


@pytest.mark.skipif(_RSVG is None, reason="rsvg-convert not installed")
def test_render_views_third_angle_layout(tmp_path: Path) -> None:
    from mech.views import render_views

    result = render_views(_step(tmp_path))
    svg = Path(result.svg_path).read_text(encoding="utf-8")
    assert "third-angle projection" in svg
    assert "units mm" in svg
    # row 0 = [top, iso], row 1 = [front, right]: labels' x/y order
    label_y = {label: svg.index(f">{label}<") for label in ("top", "isometric", "front", "right")}
    assert label_y["top"] < label_y["front"]
    assert label_y["isometric"] < label_y["front"]


def test_mcp_render_views(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if _RSVG is None:
        pytest.skip("rsvg-convert not installed")
    from mcp import types

    from mech.mcp_server import call_tool

    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    step = _step(tmp_path)
    result = call_tool("mech_render_views", {"step": str(step)})
    assert not result.isError
    import json

    text_block = result.content[0]
    assert isinstance(text_block, types.TextContent)
    payload = json.loads(text_block.text)
    assert payload["verdict"] == "pass"
    assert payload["views"] == ["front", "top", "right", "isometric"]
    images = [c for c in result.content if isinstance(c, types.ImageContent)]
    assert len(images) == 1 and images[0].mimeType == "image/png"


def test_mcp_render_views_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from mech.mcp_server import call_tool

    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    assert call_tool("mech_render_views", {"step": "nope.step"}).isError


def test_screen_basis_matches_project_to_viewport() -> None:
    # u = normalize(up x dir), v = dir x u — same basis project_to_viewport uses.
    from mech.views import _project_point, _screen_basis

    # front: viewer at -Y (direction (0,-1,0)), up +Z → +X right, +Z up
    u, v = _screen_basis((0, -1, 0), (0, 0, 1))
    assert u == pytest.approx((1.0, 0.0, 0.0))
    assert v == pytest.approx((0.0, 0.0, 1.0))
    # top: viewer at +Z, up +Y → +X right, +Y up
    u, v = _screen_basis((0, 0, 1), (0, 1, 0))
    assert u == pytest.approx((1.0, 0.0, 0.0))
    assert v == pytest.approx((0.0, 1.0, 0.0))
    # right: viewer at +X, up +Z → +Y right, +Z up
    u, v = _screen_basis((1, 0, 0), (0, 0, 1))
    assert u == pytest.approx((0.0, 1.0, 0.0))
    assert v == pytest.approx((0.0, 0.0, 1.0))

    pt = _project_point((3.0, 4.0, 5.0), (0.0, 0.0, 0.0), (1, 0, 0), (0, 0, 1))
    assert pt == pytest.approx((4.0, 5.0))
    # non-unit direction is normalized
    pt = _project_point((3.0, 4.0, 5.0), (0.0, 0.0, 0.0), (2, 0, 0), (0, 0, 1))
    assert pt == pytest.approx((4.0, 5.0))
    # center offsets the projection
    pt = _project_point((3.0, 4.0, 5.0), (0.0, 4.0, 0.0), (1, 0, 0), (0, 0, 1))
    assert pt == pytest.approx((0.0, 5.0))


def test_lines_bbox() -> None:
    from mech.views import _lines_bbox

    assert _lines_bbox([[(1.0, 2.0), (3.0, 4.0)], [(-1.0, 5.0)]]) == (
        -1.0,
        3.0,
        2.0,
        5.0,
    )


def test_polylines_svg() -> None:
    from mech.views import _polylines_svg

    out = _polylines_svg([[(1.0, 2.0), (3.0, 4.0)]], (10.0, 20.0), 2.0, "s")
    assert out == ['<polyline points="12.000,16.000 16.000,12.000" fill="none" s/>']


def test_anchor_marks_svg() -> None:
    from mech.views import _anchor_marks_svg

    out = _anchor_marks_svg([("clip-1", (2.0, 3.0))], (10.0, 20.0), 2.0)
    assert len(out) == 4
    assert out[0].startswith('<circle cx="14.000" cy="14.000" r="1.5"')
    assert "clip-1" in out[3]
    assert out[3].startswith("<text")


def test_load_envelope_anchors(tmp_path: Path) -> None:
    from mech.views import _load_envelope_anchors

    envelope = _write_envelope_with_sidecar(
        tmp_path,
        [{"name": "a", "position_mm": [1.0, 2.0, 3.0]}],
        [-1.0, -2.0, -3.0],
    )
    assert _load_envelope_anchors(envelope) == [("a", (0.0, 0.0, 0.0))]

    # anchors without name/position are skipped
    tmp_path.joinpath("demo.envelope.json").write_text(
        json.dumps(
            {
                "anchors": [
                    {"name": "no-pos"},
                    {"position_mm": [1, 2, 3]},
                    {"name": "short", "position_mm": [1, 2]},
                    "not-a-dict",
                    {"name": "ok", "position_mm": [1, 0, 0]},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert _load_envelope_anchors(envelope) == [("ok", (0.0, -2.0, -3.0))]


def test_load_envelope_anchors_fail_closed(tmp_path: Path) -> None:
    from mech.views import _load_envelope_anchors

    with pytest.raises(RenderError, match="envelope file missing"):
        _load_envelope_anchors(tmp_path / "nope.envelope.json")

    bad = tmp_path / "bad.envelope.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(RenderError, match="cannot read envelope"):
        _load_envelope_anchors(bad)

    envelope = tmp_path / "demo.envelope.json"
    envelope.write_text('{"anchors": []}', encoding="utf-8")
    with pytest.raises(RenderError, match="provenance sidecar"):
        _load_envelope_anchors(envelope)

    sidecar = tmp_path / "demo.envelope.provenance.json"
    sidecar.write_text("{bad", encoding="utf-8")
    with pytest.raises(RenderError, match="provenance sidecar"):
        _load_envelope_anchors(envelope)

    sidecar.write_text("[1,2]", encoding="utf-8")
    with pytest.raises(RenderError, match="not an object"):
        _load_envelope_anchors(envelope)

    sidecar.write_text(
        json.dumps({"anchor_frame": "other", "step_frame_offset_mm": [0, 0, 0]}),
        encoding="utf-8",
    )
    with pytest.raises(RenderError, match="anchor_frame"):
        _load_envelope_anchors(envelope)

    for offset in (None, [0, 0], ["a", 0, 0]):
        sidecar.write_text(
            json.dumps(
                {
                    "anchor_frame": "assembly-bbox-min-corner",
                    "step_frame_offset_mm": offset,
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(RenderError, match="step_frame_offset_mm"):
            _load_envelope_anchors(envelope)

    sidecar.write_text(
        json.dumps(
            {
                "anchor_frame": "assembly-bbox-min-corner",
                "step_frame_offset_mm": [0, 0, 0],
            }
        ),
        encoding="utf-8",
    )
    envelope.write_text('{"anchors": "not-a-list"}', encoding="utf-8")
    with pytest.raises(RenderError, match="no anchors list"):
        _load_envelope_anchors(envelope)

    envelope.write_text('{"anchors": []}', encoding="utf-8")
    with pytest.raises(RenderError, match="no anchors with position_mm"):
        _load_envelope_anchors(envelope)


def test_render_author_outputs(tmp_path: Path, enclosure_brief: DesignBrief) -> None:
    from mech.views import render_author_outputs

    out_dir = tmp_path / "out"
    design = generate(enclosure_brief)
    export_design(enclosure_brief, design, out_dir)
    if _RSVG is None:
        with pytest.raises(RenderError):
            render_author_outputs(enclosure_brief.name, ["shell"], out_dir)
        return
    renders = render_author_outputs(
        enclosure_brief.name,
        [p.part_id for p in design.parts] if hasattr(design, "parts") else ["shell"],
        out_dir,
    )
    kinds = {r["kind"] for r in renders}
    assert kinds == {"dxf", "views"}
    for r in renders:
        assert Path(r["png_path"]).is_file()
        assert len(r["image_sha256"]) == 64
