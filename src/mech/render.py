"""Rasterize exported DXF drawings to PNG for the advisory vision lane.

The DXF projection is converted to SVG in-process (ezdxf drawing addons —
no new Python dependency) and rasterized by the system `rsvg-convert`
binary installed in the tools image. A missing rasterizer raises
RenderError — the vision lane is advisory and degrades, never guesses.

An optional sha256 visual baseline records or compares the produced PNG,
giving a deterministic regression signal between design revisions without
a vision model.
"""

# ezdxf's annotations are only partially typed.
# pyright: reportPrivateImportUsage=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

_RSVG_ENV = "MECH_RSVG_CONVERT"

BaselineVerdict = Literal["match", "diff", "recorded"]


class RenderError(RuntimeError):
    """Raised when a DXF cannot be rendered to PNG."""


@dataclass(frozen=True)
class RenderResult:
    dxf_path: str
    svg_path: str
    png_path: str
    image_sha256: str
    baseline: BaselineVerdict | None = None
    baseline_sha256: str | None = None


def _command(env_name: str, default: str) -> list[str]:
    return shlex.split(os.environ.get(env_name, default))


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RenderError(
            f"{command[0]} is not available; install the librsvg2-bin apt package "
            f"or set {_RSVG_ENV} to an rsvg-convert-compatible binary"
        ) from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RenderError(f"rasterizer failed: {exc}") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dxf_to_svg(dxf_path: Path, svg_path: Path, *, margin_mm: float = 5.0) -> None:
    try:
        import ezdxf
        from ezdxf import bbox
        from ezdxf.addons.drawing import layout
        from ezdxf.addons.drawing.frontend import Frontend
        from ezdxf.addons.drawing.properties import RenderContext
        from ezdxf.addons.drawing.svg import SVGBackend
    except ImportError as exc:
        raise RenderError(f"ezdxf drawing addons unavailable: {exc}") from exc
    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception as exc:
        raise RenderError(f"cannot read DXF {dxf_path}: {exc}") from exc
    modelspace = doc.modelspace()
    extents = bbox.extents(modelspace)
    if not extents.has_data:
        raise RenderError(f"DXF has no modelspace entities: {dxf_path}")
    context = RenderContext(doc)
    backend = SVGBackend()
    Frontend(context, backend).draw_layout(modelspace, finalize=True)
    page = layout.Page(
        extents.size.x,
        extents.size.y,
        units=layout.Units.mm,
        margins=layout.Margins.all(margin_mm),
    )
    svg_path.write_text(backend.get_string(page), encoding="utf-8")


def _record_or_compare_baseline(
    png_path: Path, baseline_path: Path
) -> tuple[BaselineVerdict, str | None]:
    """Write or compare a sha256 visual baseline for `png_path`."""
    image_sha = _sha256(png_path)
    if not baseline_path.is_file():
        record = {
            "image": str(png_path),
            "image_sha256": image_sha,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return "recorded", None
    try:
        old = json.loads(baseline_path.read_text(encoding="utf-8"))
        old_sha = old["image_sha256"]
    except (OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise RenderError(f"cannot read baseline {baseline_path}: {exc}") from exc
    if not isinstance(old_sha, str):
        raise RenderError(f"baseline {baseline_path} has no image_sha256 string")
    return ("match" if old_sha == image_sha else "diff"), old_sha


def render_dxf(
    dxf_path: Path,
    out_path: Path | None = None,
    *,
    dpi: int = 200,
    baseline_path: Path | None = None,
) -> RenderResult:
    """Render `dxf_path` to PNG; optionally record/compare a sha256 baseline."""
    if not dxf_path.is_file() or dxf_path.stat().st_size == 0:
        raise RenderError(f"render source is missing or empty: {dxf_path}")
    if dxf_path.suffix.lower() != ".dxf":
        raise RenderError(f"render source is not a .dxf file: {dxf_path}")
    if dpi <= 0:
        raise RenderError("dpi must be positive")
    png_path = out_path or dxf_path.with_suffix(".png")
    svg_path = png_path.with_suffix(".svg")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    _dxf_to_svg(dxf_path, svg_path)
    result = _run(
        [
            *_command(_RSVG_ENV, "rsvg-convert"),
            "-d",
            str(dpi),
            str(svg_path),
            "-o",
            str(png_path),
        ]
    )
    if result.returncode != 0 or not png_path.is_file():
        raise RenderError(
            f"rsvg-convert failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    baseline: BaselineVerdict | None = None
    baseline_sha: str | None = None
    if baseline_path is not None:
        baseline, baseline_sha = _record_or_compare_baseline(png_path, baseline_path)
    return RenderResult(
        dxf_path=str(dxf_path),
        svg_path=str(svg_path),
        png_path=str(png_path),
        image_sha256=_sha256(png_path),
        baseline=baseline,
        baseline_sha256=baseline_sha,
    )
