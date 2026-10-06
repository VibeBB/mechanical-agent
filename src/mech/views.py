"""Project a STEP model into a 2x2 engineering views sheet (SVG + PNG).

Four orthographic views (front, top, right, isometric) are computed with
build123d's ``Compound.project_to_viewport``: visible edges are drawn
solid, hidden edges thin dashed gray. The sheet uses the standard
**third-angle** arrangement — top above front, right-side view beside
front, isometric in the spare corner — i.e. row 1 = [top, isometric],
row 2 = [front, right]. Projection is orthographic with one uniform
scale across the four cells; each view is centered in its own cell and
labelled, and a footer records the STEP file name plus the overall
bounding-box dimensions (units mm throughout).

Axis conventions (verified by ``tests/test_render.py``):

* front — viewer at -Y looking +Y, up +Z: screen +x is model +X,
  screen +y is model +Z.
* top — viewer at +Z looking -Z, up +Y: screen +x is model +X,
  screen +y is model +Y (the part's front, -Y, is the bottom edge so it
  borders the front view below).
* right — viewer at +X looking -X, up +Z: screen +x is model +Y and
  screen +y is model +Z (the left edge borders the front view's right
  edge, as third-angle requires).

``project_to_viewport`` returns edge geometry in the viewport plane with
the look-at point as 2D origin, so a model point ``p`` maps to
``((p - center) . u, (p - center) . v)`` with ``u = normalize(up x dir)``
and ``v = dir x u`` — the same basis the envelope anchor overlay uses.

An optional ``envelope_path`` overlays the wire-agent harness anchors:
the sibling ``<name>.envelope.provenance.json`` must carry
``anchor_frame: "assembly-bbox-min-corner"`` and ``step_frame_offset_mm``
(the assembly bbox minimum in the STEP frame), so each anchor's
``position_mm`` is translated into STEP coordinates and drawn as a
circle + cross + name in all four views. A missing or malformed sidecar
raises ``RenderError`` (fail-closed).

The sheet is written as ``<step stem>.views.svg`` beside the STEP and
rasterized to ``.views.png`` by the same rsvg-convert path ``render.py``
uses — a missing rasterizer or a projection failure raises
``RenderError``.

"""

# build123d's annotations are only partially typed.
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .render import (
    BaselineVerdict,
    RenderError,
    rasterize_svg,
    record_or_compare_baseline,
    sha256_file,
)
from .workspace import reject_symlinks

ViewName = str

_ANCHOR_FRAME = "assembly-bbox-min-corner"


@dataclass(frozen=True)
class ViewsResult:
    step_path: str
    svg_path: str
    png_path: str
    image_sha256: str
    views: tuple[ViewName, ...]
    baseline: BaselineVerdict | None = None
    baseline_sha256: str | None = None


# (label, viewport direction, viewport up, cell column, cell row)
# Third-angle layout: row 0 = [top, isometric], row 1 = [front, right].
_VIEW_LAYOUT: tuple[
    tuple[ViewName, tuple[float, float, float], tuple[float, float, float], int, int], ...
] = (
    ("top", (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), 0, 0),
    ("isometric", (1.0, -1.0, 1.0), (0.0, 0.0, 1.0), 1, 0),
    ("front", (0.0, -1.0, 0.0), (0.0, 0.0, 1.0), 0, 1),
    ("right", (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 1, 1),
)

_VIEW_NAMES: tuple[ViewName, ...] = ("front", "top", "right", "isometric")

_SAMPLES = 64
_MARGIN_MM = 12.0
_LABEL_H_MM = 6.0
_FOOTER_H_MM = 8.0
_ANCHOR_R_MM = 1.5
_ANCHOR_CROSS_MM = 2.5


def _norm(v: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return (v[0] / length, v[1] / length, v[2] / length)


def _cross(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _screen_basis(
    direction: tuple[float, float, float], up: tuple[float, float, float]
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Screen x/y basis vectors matching ``project_to_viewport``: u = up x dir, v = dir x u."""
    d = _norm(direction)
    u = _norm(_cross(up, d))
    v = _cross(d, u)
    return u, v


def _project_point(
    point: tuple[float, float, float],
    center: tuple[float, float, float],
    direction: tuple[float, float, float],
    up: tuple[float, float, float],
) -> tuple[float, float]:
    """2D screen coordinates of a 3D point under the view's projection basis."""
    u, v = _screen_basis(direction, up)
    rel = (point[0] - center[0], point[1] - center[1], point[2] - center[2])
    return (
        rel[0] * u[0] + rel[1] * u[1] + rel[2] * u[2],
        rel[0] * v[0] + rel[1] * v[1] + rel[2] * v[2],
    )


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


def _lines_bbox(lines: list[list[tuple[float, float]]]) -> tuple[float, float, float, float]:
    lo_x = lo_y = float("inf")
    hi_x = hi_y = float("-inf")
    for line in lines:
        for x, y in line:
            lo_x, lo_y = min(lo_x, x), min(lo_y, y)
            hi_x, hi_y = max(hi_x, x), max(hi_y, y)
    return lo_x, hi_x, lo_y, hi_y


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


def _load_envelope_anchors(
    envelope_path: Path,
) -> list[tuple[str, tuple[float, float, float]]]:
    """Anchor positions translated into the STEP frame via the provenance sidecar."""
    if not envelope_path.is_file():
        raise RenderError(f"envelope file missing: {envelope_path}")
    try:
        envelope: Any = json.loads(envelope_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RenderError(f"cannot read envelope {envelope_path}: {exc}") from exc
    sidecar_path = envelope_path.with_suffix(".provenance.json")
    try:
        sidecar: Any = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RenderError(
            f"envelope overlay needs the provenance sidecar "
            f"{sidecar_path.name} (anchor_frame + step_frame_offset_mm): {exc}"
        ) from exc
    if not isinstance(sidecar, dict):
        raise RenderError(f"envelope provenance sidecar is not an object: {sidecar_path}")
    provenance = cast(dict[str, Any], sidecar)
    frame = provenance.get("anchor_frame")
    if frame != _ANCHOR_FRAME:
        raise RenderError(
            f"envelope overlay needs anchor_frame {_ANCHOR_FRAME!r} "
            f"in {sidecar_path.name}, found {frame!r}"
        )
    offset = provenance.get("step_frame_offset_mm")
    if (
        not isinstance(offset, list)
        or len(offset) != 3
        or not all(isinstance(v, int | float) for v in offset)
    ):
        raise RenderError(
            f"envelope overlay needs step_frame_offset_mm [x,y,z] in {sidecar_path.name}"
        )
    anchors_raw: Any = envelope.get("anchors") if isinstance(envelope, dict) else None
    if not isinstance(anchors_raw, list):
        raise RenderError(f"envelope has no anchors list: {envelope_path}")
    anchors: list[tuple[str, tuple[float, float, float]]] = []
    for item in cast(list[Any], anchors_raw):
        if not isinstance(item, dict):
            continue
        anchor = cast(dict[str, Any], item)
        position = anchor.get("position_mm")
        name = anchor.get("name")
        if position is None or name is None:
            continue
        pos = cast(list[Any], position)
        if len(pos) != 3:
            continue
        anchors.append(
            (
                str(name),
                (
                    float(pos[0]) + float(offset[0]),
                    float(pos[1]) + float(offset[1]),
                    float(pos[2]) + float(offset[2]),
                ),
            )
        )
    if not anchors:
        raise RenderError(f"envelope has no anchors with position_mm: {envelope_path}")
    return anchors


def _anchor_marks_svg(
    anchors: list[tuple[str, tuple[float, float]]],
    offset: tuple[float, float],
    scale: float,
) -> list[str]:
    """Circle + cross + name per anchor in one view cell (screen coords)."""
    out: list[str] = []
    style = 'stroke="#c33" stroke-width="0.3" fill="none"'
    for name, (x, y) in anchors:
        sx = offset[0] + x * scale
        sy = offset[1] - y * scale
        r = _ANCHOR_R_MM
        c = _ANCHOR_CROSS_MM
        out.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="{r}" {style}/>')
        out.append(f'<polyline points="{sx - c:.3f},{sy:.3f} {sx + c:.3f},{sy:.3f}" {style}/>')
        out.append(f'<polyline points="{sx:.3f},{sy - c:.3f} {sx:.3f},{sy + c:.3f}" {style}/>')
        out.append(
            f'<text x="{sx + c + 1:.3f}" y="{sy - c - 0.5:.3f}" font-size="3" '
            f'font-family="sans-serif" fill="#c33">{name}</text>'
        )
    return out


def render_views(
    step_path: Path,
    *,
    envelope_path: Path | None = None,
    baseline_path: Path | None = None,
    dpi: int = 200,
) -> ViewsResult:
    """Render `step_path` into a 2x2 third-angle views sheet.

    ``envelope_path`` overlays harness anchors (requires the provenance
    sidecar with ``step_frame_offset_mm``); ``baseline_path`` records or
    compares a sha256 image baseline.
    """
    if not step_path.is_file() or step_path.stat().st_size == 0:
        raise RenderError(f"render source is missing or empty: {step_path}")
    if step_path.suffix.lower() not in (".step", ".stp"):
        raise RenderError(f"render source is not a .step file: {step_path}")
    reject_symlinks(step_path)
    if envelope_path is not None:
        reject_symlinks(envelope_path)
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

    anchors_3d: list[tuple[str, tuple[float, float, float]]] = []
    if envelope_path is not None:
        anchors_3d = _load_envelope_anchors(envelope_path)

    cells: list[dict[str, Any]] = []
    for label, direction, up, col, row in _VIEW_LAYOUT:
        visible, hidden = _view_geometry(compound, center, direction, up)
        anchors_2d = [
            (name, _project_point(point, center, direction, up)) for name, point in anchors_3d
        ]
        cells.append(
            {
                "label": label,
                "col": col,
                "row": row,
                "visible": visible,
                "hidden": hidden,
                "anchors": anchors_2d,
            }
        )

    # one uniform scale across the four cells: the cell size comes from the
    # largest per-view span on each axis; each view is centered in its cell.
    scale = 1.0  # model units are mm; 1 model unit -> 1 svg unit (mm)
    span_x = span_y = 1.0
    for cell in cells:
        lo_x, hi_x, lo_y, hi_y = _lines_bbox([*cell["visible"], *cell["hidden"]])
        if math.isfinite(lo_x):
            span_x = max(span_x, hi_x - lo_x)
            span_y = max(span_y, hi_y - lo_y)
    else_has_edges = any(cell["visible"] or cell["hidden"] for cell in cells)
    if not else_has_edges:
        raise RenderError(f"projection produced no edges: {step_path}")
    cell_w = span_x + 2 * _MARGIN_MM
    cell_h = span_y + 2 * _MARGIN_MM + _LABEL_H_MM
    page_w = cell_w * 2
    page_h = cell_h * 2 + _FOOTER_H_MM

    dims = f"{bounds.size.X:.1f} x {bounds.size.Y:.1f} x {bounds.size.Z:.1f} mm (W x D x H)"
    solid = 'stroke="#111" stroke-width="0.35"'
    hidden_style = 'stroke="#888" stroke-width="0.15" stroke-dasharray="1.2,0.9"'

    svg: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_w:.1f}mm" '
        f'height="{page_h:.1f}mm" viewBox="0 0 {page_w:.3f} {page_h:.3f}">',
        f'<rect x="0" y="0" width="{page_w:.3f}" height="{page_h:.3f}" fill="#fff"/>',
    ]
    for cell in cells:
        cell_x = cell["col"] * cell_w
        cell_y = cell["row"] * cell_h
        all_lines = [*cell["visible"], *cell["hidden"]]
        if all_lines:
            lo_x, hi_x, lo_y, hi_y = _lines_bbox(all_lines)
            view_w = (hi_x - lo_x) * scale
            view_h = (hi_y - lo_y) * scale
            cx = (lo_x + hi_x) / 2 * scale
            cy = (lo_y + hi_y) / 2 * scale
            ox = cell_x + _MARGIN_MM + (span_x * scale - view_w) / 2 + (view_w / 2 - cx)
            oy = cell_y + _MARGIN_MM + _LABEL_H_MM + (span_y * scale - view_h) / 2 + view_h / 2 + cy
        else:
            ox = cell_x + _MARGIN_MM
            oy = cell_y + _MARGIN_MM + _LABEL_H_MM
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
        if cell["anchors"]:
            svg.extend(_anchor_marks_svg(cell["anchors"], (ox, oy), scale))
    svg.append(
        f'<text x="{_MARGIN_MM:.3f}" y="{page_h - 3:.3f}" font-size="3" '
        f'font-family="sans-serif">third-angle projection, scale uniform, units mm '
        f"— {step_path.name} — overall: {dims}</text>"
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
        views=_VIEW_NAMES,
        baseline=baseline,
        baseline_sha256=baseline_sha,
    )


def render_author_outputs(
    name: str, part_ids: list[str], out_dir: Path, *, dpi: int = 200
) -> list[dict[str, Any]]:
    """Render every exported DXF plus a views sheet per STEP (advisory, L2).

    Called after authoring so the design has vision points before review.
    Raises ``RenderError`` on the first render failure — the caller
    reports it under ``renders: {status: "error", ...}``; it never
    touches gate verdicts.
    """
    from .render import render_dxf

    renders: list[dict[str, Any]] = []
    for dxf_path in sorted(out_dir.glob("*.dxf")):
        result = render_dxf(dxf_path, dpi=dpi)
        renders.append(
            {
                "kind": "dxf",
                "source": str(dxf_path),
                "png_path": result.png_path,
                "image_sha256": result.image_sha256,
            }
        )
    step_paths = [out_dir / f"{name}.step"] + [
        out_dir / f"{name}-{part_id}.step" for part_id in part_ids
    ]
    for step in step_paths:
        if not step.is_file():
            continue
        result = render_views(step, dpi=dpi)
        renders.append(
            {
                "kind": "views",
                "source": str(step),
                "png_path": result.png_path,
                "image_sha256": result.image_sha256,
            }
        )
    return renders


# axis -> (viewport direction, viewport up) of the view that looks at the cut
# face; the kept half lies behind the plane (away from the viewer).
_SECTION_VIEWS: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "x": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "y": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "z": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
}
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
_PLANE_TOL_MM = 1e-6
_MIN_CUT_DEPTH_MM = 1e-3
_SECTION_MIN_PAGE_W_MM = 170.0


@dataclass(frozen=True)
class SectionResult:
    step_path: str
    svg_path: str
    png_path: str
    image_sha256: str
    axis: str
    plane_mm: float
    section_area_mm2: float
    region_count: int
    baseline: BaselineVerdict | None = None
    baseline_sha256: str | None = None


def _component(vector: Any, index: int) -> float:
    return float((vector.X, vector.Y, vector.Z)[index])


def _face_loops(
    face: Any,
    center: tuple[float, float, float],
    direction: tuple[float, float, float],
    up: tuple[float, float, float],
) -> list[list[tuple[float, float]]]:
    loops: list[list[tuple[float, float]]] = []
    for wire in [face.outer_wire(), *face.inner_wires()]:
        loop: list[tuple[float, float]] = []
        for edge in wire.order_edges():
            try:
                length = float(edge.length)
            except Exception:
                length = 1.0
            count = max(4, min(_SAMPLES, int(length * 2) + 1))
            for i in range(count):
                p = edge.position_at(i / count)
                loop.append(_project_point((p.X, p.Y, p.Z), center, direction, up))
        if loop:
            loops.append(loop)
    return loops


def render_section(
    step_path: Path,
    *,
    axis: str,
    offset_mm: float = 0.0,
    baseline_path: Path | None = None,
    dpi: int = 200,
) -> SectionResult:
    """Render a hatched cross-section of `step_path` cut normal to `axis`.

    The plane passes through the bounding-box centre shifted by
    ``offset_mm`` along ``axis``; the half behind the plane (as seen from
    the matching front/right/top view) is projected and every cut face is
    hatched. A plane outside the part, or one that cuts no material,
    raises ``RenderError``.
    """
    if axis not in _SECTION_VIEWS:
        raise RenderError(f"section axis must be one of x, y, z: {axis!r}")
    if not math.isfinite(offset_mm):
        raise RenderError("section offset must be finite")
    if not step_path.is_file() or step_path.stat().st_size == 0:
        raise RenderError(f"section source is missing or empty: {step_path}")
    if step_path.suffix.lower() not in (".step", ".stp"):
        raise RenderError(f"section source is not a .step file: {step_path}")
    reject_symlinks(step_path)
    if dpi <= 0:
        raise RenderError("dpi must be positive")
    try:
        from build123d import Keep, Plane, import_step, split
    except ImportError as exc:
        raise RenderError(f"build123d unavailable: {exc}") from exc
    try:
        compound = import_step(step_path)
        bounds = compound.bounding_box()
    except Exception as exc:
        raise RenderError(f"cannot import STEP {step_path}: {exc}") from exc
    lo = (bounds.min.X, bounds.min.Y, bounds.min.Z)
    hi = (bounds.max.X, bounds.max.Y, bounds.max.Z)
    center = tuple((a + b) / 2 for a, b in zip(lo, hi, strict=True))
    index = _AXIS_INDEX[axis]
    plane_at = center[index] + offset_mm
    if not lo[index] + _MIN_CUT_DEPTH_MM < plane_at < hi[index] - _MIN_CUT_DEPTH_MM:
        raise RenderError(
            f"section plane {axis}={plane_at:.3f} mm lies outside the part "
            f"({lo[index]:.3f}..{hi[index]:.3f} mm)"
        )
    direction, up = _SECTION_VIEWS[axis]
    keep_dir = (-direction[0], -direction[1], -direction[2])
    origin = list(center)
    origin[index] = plane_at
    try:
        cut = split(
            compound,
            bisect_by=Plane(origin=tuple(origin), z_dir=keep_dir),
            keep=Keep.TOP,
        )
        faces = [
            face
            for face in cut.faces()
            if abs(_component(face.center(), index) - plane_at) <= _PLANE_TOL_MM
            and abs(abs(_component(face.normal_at(), index)) - 1.0) <= 1e-9
        ]
    except Exception as exc:
        raise RenderError(f"section cut failed: {exc}") from exc
    if not faces:
        raise RenderError(f"section plane {axis}={plane_at:.3f} mm cuts no material")
    view_center = cast(tuple[float, float, float], tuple(origin))
    visible, _hidden = _view_geometry(cut, view_center, direction, up)
    regions = [_face_loops(face, view_center, direction, up) for face in faces]
    area = sum(float(face.area) for face in faces)

    all_lines = [*visible, *(loop for region in regions for loop in region)]
    lo_x, hi_x, lo_y, hi_y = _lines_bbox(all_lines)
    view_w = hi_x - lo_x
    view_h = hi_y - lo_y
    page_w = max(view_w + 2 * _MARGIN_MM, _SECTION_MIN_PAGE_W_MM)
    page_h = view_h + 2 * _MARGIN_MM + _LABEL_H_MM + _FOOTER_H_MM
    ox = (page_w - view_w) / 2 - lo_x
    oy = _MARGIN_MM + _LABEL_H_MM + hi_y
    solid = 'stroke="#111" stroke-width="0.35"'
    hatch_style = 'fill="url(#section-hatch)" stroke="#111" stroke-width="0.5"'
    label = f"SECTION {axis.upper()}-{axis.upper()} ({axis} = {plane_at:.2f} mm)"
    svg: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_w:.1f}mm" '
        f'height="{page_h:.1f}mm" viewBox="0 0 {page_w:.3f} {page_h:.3f}">',
        '<defs><pattern id="section-hatch" patternUnits="userSpaceOnUse" width="2" '
        'height="2" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="2" '
        'stroke="#111" stroke-width="0.25"/></pattern></defs>',
        f'<rect x="0" y="0" width="{page_w:.3f}" height="{page_h:.3f}" fill="#fff"/>',
        f'<text x="2" y="{_LABEL_H_MM - 1:.3f}" font-size="3.5" '
        f'font-family="sans-serif">{label}</text>',
    ]
    svg.extend(_polylines_svg(visible, (ox, oy), 1.0, solid))
    for region in regions:
        path = " ".join(
            "M " + " L ".join(f"{ox + x:.3f},{oy - y:.3f}" for x, y in loop) + " Z"
            for loop in region
        )
        svg.append(f'<path d="{path}" fill-rule="evenodd" {hatch_style}/>')
    svg.append(
        f'<text x="{_MARGIN_MM:.3f}" y="{page_h - 3:.3f}" font-size="3" '
        f'font-family="sans-serif">section view, scale 1:1, units mm — {step_path.name} — '
        f"cut area {area:.1f} mm2 in {len(faces)} region(s)</text>"
    )
    svg.append("</svg>")

    svg_path = step_path.with_suffix(f".section-{axis}.svg")
    png_path = step_path.with_suffix(f".section-{axis}.png")
    svg_path.write_text("\n".join(svg) + "\n", encoding="utf-8")
    rasterize_svg(svg_path, png_path, dpi)
    baseline: BaselineVerdict | None = None
    baseline_sha: str | None = None
    if baseline_path is not None:
        baseline, baseline_sha = record_or_compare_baseline(png_path, baseline_path)
    return SectionResult(
        step_path=str(step_path),
        svg_path=str(svg_path),
        png_path=str(png_path),
        image_sha256=sha256_file(png_path),
        axis=axis,
        plane_mm=plane_at,
        section_area_mm2=area,
        region_count=len(faces),
        baseline=baseline,
        baseline_sha256=baseline_sha,
    )
