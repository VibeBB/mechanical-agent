"""Project a STEP model into a 2x2 engineering views sheet (SVG + PNG).

Four orthographic views (front, top, right, isometric) are computed with
build123d's ``Compound.project_to_viewport``: visible edges are drawn
solid, hidden edges thin dashed gray, and each cell is labelled with the
view name plus the overall bounding-box dimensions. The sheet is written
as ``<step stem>.views.svg`` beside the STEP and rasterized to
``.views.png`` by the same rsvg-convert path ``render.py`` uses — a
missing rasterizer or a projection failure raises ``RenderError``
(fail-closed).

"""

# build123d's annotations are only partially typed.
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .render import (
    BaselineVerdict,
    RenderError,
    rasterize_svg,
    record_or_compare_baseline,
    sha256_file,
)
from .workspace import reject_symlinks

ViewName = str


@dataclass(frozen=True)
class ViewsResult:
    step_path: str
    svg_path: str
    png_path: str
    image_sha256: str
    views: tuple[ViewName, ...]
    baseline: BaselineVerdict | None = None
    baseline_sha256: str | None = None


_VIEW_LAYOUT: tuple[
    tuple[ViewName, tuple[float, float, float], tuple[float, float, float]], ...
] = (
    # (label, viewport direction, viewport up)
    ("front", (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    ("top", (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
    ("right", (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ("isometric", (1.0, -1.0, 1.0), (0.0, 0.0, 1.0)),
)

_SAMPLES = 64
_MARGIN_MM = 12.0
_LABEL_H_MM = 6.0


def _norm(v: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return (v[0] / length, v[1] / length, v[2] / length)


def _edge_polyline(edge: Any) -> list[tuple[float, float]]:
    try:
        length = float(edge.length)
    except Exception:
        length = 1.0
    count = max(4, min(_SAMPLES, int(length * 2) + 1))
    points: list[tuple[float, float]] = []
    for i in range(count + 1):
        p = edge.position_at(i / count)
        points.append((float(p.X), float(p.Y)))
    return points


def _view_geometry(
    compound: Any,
    center: tuple[float, float, float],
    direction: tuple[float, float, float],
    up: tuple[float, float, float],
) -> tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]]]:
    distance = 10.0 * (math.sqrt(sum(c * c for c in compound.bounding_box().size)) + 1.0)
    d = _norm(direction)
    origin = (
        center[0] + d[0] * distance,
        center[1] + d[1] * distance,
        center[2] + d[2] * distance,
    )
    try:
        visible, hidden = compound.project_to_viewport(origin, up, look_at=tuple(center))
    except Exception as exc:
        raise RenderError(f"projection failed: {exc}") from exc
    return (
        [_edge_polyline(edge) for edge in visible],
        [_edge_polyline(edge) for edge in hidden],
    )


def _polylines_svg(
    polylines: list[list[tuple[float, float]]],
    offset: tuple[float, float],
    scale: float,
    style: str,
) -> list[str]:
    out: list[str] = []
    for line in polylines:
        pts = " ".join(f"{offset[0] + x * scale:.3f},{offset[1] - y * scale:.3f}" for x, y in line)
        out.append(f'<polyline points="{pts}" fill="none" {style}/>')
    return out


def render_views(
    step_path: Path,
    *,
    baseline_path: Path | None = None,
    dpi: int = 200,
) -> ViewsResult:
    """Render `step_path` into a 2x2 views sheet; optionally compare a baseline."""
    if not step_path.is_file() or step_path.stat().st_size == 0:
        raise RenderError(f"render source is missing or empty: {step_path}")
    if step_path.suffix.lower() not in (".step", ".stp"):
        raise RenderError(f"render source is not a .step file: {step_path}")
    reject_symlinks(step_path)
    if dpi <= 0:
        raise RenderError("dpi must be positive")
    try:
        from build123d import import_step
    except ImportError as exc:
        raise RenderError(f"build123d unavailable: {exc}") from exc
    try:
        compound = import_step(step_path)
        bounds = compound.bounding_box()
        _ = bounds.size
    except Exception as exc:
        raise RenderError(f"cannot import STEP {step_path}: {exc}") from exc
    center = (
        bounds.min.X + bounds.size.X / 2,
        bounds.min.Y + bounds.size.Y / 2,
        bounds.min.Z + bounds.size.Z / 2,
    )

    cells: list[dict[str, Any]] = []
    for label, direction, up in _VIEW_LAYOUT:
        visible, hidden = _view_geometry(compound, center, direction, up)
        cells.append({"label": label, "visible": visible, "hidden": hidden})

    # uniform scale across all four cells so views stay comparable
    lo_x = lo_y = float("inf")
    hi_x = hi_y = float("-inf")
    for cell in cells:
        for line in (*cell["visible"], *cell["hidden"]):
            for x, y in line:
                lo_x, lo_y = min(lo_x, x), min(lo_y, y)
                hi_x, hi_y = max(hi_x, x), max(hi_y, y)
    if not math.isfinite(lo_x):
        raise RenderError(f"projection produced no edges: {step_path}")
    span_x = max(hi_x - lo_x, 1.0)
    span_y = max(hi_y - lo_y, 1.0)
    cell_w = span_x + 2 * _MARGIN_MM
    cell_h = span_y + 2 * _MARGIN_MM + _LABEL_H_MM
    page_w = cell_w * 2
    page_h = cell_h * 2
    scale = 1.0  # model units are mm; 1 model unit -> 1 svg unit (mm)

    dims = f"{bounds.size.X:.1f} x {bounds.size.Y:.1f} x {bounds.size.Z:.1f} mm (W x D x H)"
    solid = 'stroke="#111" stroke-width="0.35"'
    hidden_style = 'stroke="#888" stroke-width="0.15" stroke-dasharray="1.2,0.9"'

    svg: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_w:.1f}mm" '
        f'height="{page_h:.1f}mm" viewBox="0 0 {page_w:.3f} {page_h:.3f}">',
        f'<rect x="0" y="0" width="{page_w:.3f}" height="{page_h:.3f}" fill="#fff"/>',
    ]
    for index, cell in enumerate(cells):
        ox = (index % 2) * cell_w + _MARGIN_MM - lo_x * scale
        oy = (index // 2) * cell_h + _MARGIN_MM + _LABEL_H_MM + hi_y * scale
        cell_x = (index % 2) * cell_w
        cell_y = (index // 2) * cell_h
        svg.append(
            f'<rect x="{cell_x:.3f}" y="{cell_y:.3f}" width="{cell_w:.3f}" '
            f'height="{cell_h:.3f}" fill="none" stroke="#ccc" stroke-width="0.1"/>'
        )
        svg.append(
            f'<text x="{cell_x + 2:.3f}" y="{cell_y + _LABEL_H_MM - 1:.3f}" '
            f'font-size="3.5" font-family="sans-serif">{cell["label"]}</text>'
        )
        svg.extend(_polylines_svg(cell["hidden"], (ox, oy), scale, hidden_style))
        svg.extend(_polylines_svg(cell["visible"], (ox, oy), scale, solid))
    svg.append(
        f'<text x="{_MARGIN_MM:.3f}" y="{page_h - 2:.3f}" font-size="3" '
        f'font-family="sans-serif">overall: {dims}</text>'
    )
    svg.append("</svg>")

    png_path = step_path.with_suffix(".views.png")
    svg_path = step_path.with_suffix(".views.svg")
    svg_path.write_text("\n".join(svg) + "\n", encoding="utf-8")
    rasterize_svg(svg_path, png_path, dpi)
    baseline: BaselineVerdict | None = None
    baseline_sha: str | None = None
    if baseline_path is not None:
        baseline, baseline_sha = record_or_compare_baseline(png_path, baseline_path)
    return ViewsResult(
        step_path=str(step_path),
        svg_path=str(svg_path),
        png_path=str(png_path),
        image_sha256=sha256_file(png_path),
        views=tuple(label for label, _, _ in _VIEW_LAYOUT),
        baseline=baseline,
        baseline_sha256=baseline_sha,
    )
