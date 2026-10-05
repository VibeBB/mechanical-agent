"""DXF render tests — advisory vision-lane rasterization and visual baselines."""

# ezdxf's annotations are only partially typed.
# pyright: reportPrivateImportUsage=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

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


def test_envelope_anchors_not_in_step_frame(
    enclosure_brief_dict: dict[str, Any], tmp_path: Path
) -> None:
    """Documents why render_views has no anchor overlay: envelope anchors
    are declared in the design frame (0..width x 0..depth x 0..height of
    the enclosure) while exported STEP parts are centered, so raw
    position_mm values do not land inside the assembly bbox."""
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
    anchors = [a.position_mm for a in enclosure_brief.harness_anchors]
    assert anchors
    in_box = [
        a
        for a in anchors
        if a is not None
        and bb.min.X - 5 <= a[0] <= bb.min.X + bb.size.X + 5
        and bb.min.Y - 5 <= a[1] <= bb.min.Y + bb.size.Y + 5
        and bb.min.Z - 5 <= a[2] <= bb.min.Z + bb.size.Z + 5
    ]
    assert not in_box  # hypothesis: shared frame — false for this example
    # corner-origin reading of the same numbers does land inside the envelope
    for a in anchors:
        assert a is not None
        assert -5 <= a[0] <= bb.size.X + 5
        assert -5 <= a[1] <= bb.size.Y + 5
        assert -5 <= a[2] <= bb.size.Z + 5


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
