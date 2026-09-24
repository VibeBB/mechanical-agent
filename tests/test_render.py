"""DXF render tests — advisory vision-lane rasterization and visual baselines."""

# ezdxf's annotations are only partially typed.
# pyright: reportPrivateImportUsage=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import shutil
from pathlib import Path

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


def test_mcp_render(tmp_path: Path):
    if _RSVG is None:
        pytest.skip("rsvg-convert not installed")
    from mcp import types

    from mech.mcp_server import call_tool

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


def test_mcp_render_fail_closed(tmp_path: Path):
    from mech.mcp_server import call_tool

    result = call_tool("mech_render", {"dxf_path": str(tmp_path / "nope.dxf")})
    assert result.isError


@pytest.mark.skipif(_RSVG is None, reason="rsvg-convert not installed")
def test_render_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MECH_RSVG_CONVERT", "/nonexistent-rsvg")
    with pytest.raises(RenderError, match="not available"):
        render_dxf(_dxf(tmp_path))
