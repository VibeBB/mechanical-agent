"""Post-process OCCT outline DXFs into annotated drawings.

Adds a drawing frame, overall linear dimensions, hole diameter callouts, a
hole table with datum coordinates, center marks and hole tags, a notes block,
and a title block to each per-part DXF, using plain LINE/LWPOLYLINE/TEXT
entities (no associative DIMENSION/dimstyle dependency) so output stays
byte-stable.
"""

# ezdxf's annotations are only partially typed.
# pyright: reportPrivateImportUsage=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf import bbox

from . import __version__
from .brief import FitDeclaration

_FRAME_MARGIN_RATIO = 0.08
_TEXT_HEIGHT_RATIO = 0.030
_MIN_TEXT_HEIGHT_MM = 1.2
_ARROW_RATIO = 0.30
_DIAMETER_ANGLE_DEG = 45.0
# ezdxf stamps wall-clock datetimes, version banners, and placeholder GUIDs;
# all are pinned after saveas so exports stay byte-reproducible.
_EZDXF_VERSION_PATTERN = re.compile(r"^1\.4\.4 @ .*$", re.MULTILINE)
_GUID_PATTERN = re.compile(r"\{[0-9A-Fa-f-]{36}\}")
_NIL_GUID = "{00000000-0000-0000-0000-000000000000}"


def _fmt(value: float) -> str:
    return f"{value:.4g}"


def _text(msp: Any, content: str, point: tuple[float, float], height: float, layer: str) -> None:
    msp.add_text(
        content,
        height=height,
        dxfattribs={"layer": layer, "insert": point},
    )


def _line(msp: Any, p1: tuple[float, float], p2: tuple[float, float], layer: str) -> None:
    msp.add_line(p1, p2, dxfattribs={"layer": layer})


def _arrow(msp: Any, tip: tuple[float, float], direction: float, size: float, layer: str) -> None:
    """Solid triangular arrowhead at `tip` pointing along `direction` (deg)."""
    rad = math.radians(direction)
    ux, uy = math.cos(rad), math.sin(rad)
    px, py = -uy, ux
    half_w = size * _ARROW_RATIO / 2
    p1 = (tip[0] - ux * size + px * half_w, tip[1] - uy * size + py * half_w)
    p2 = (tip[0] - ux * size - px * half_w, tip[1] - uy * size - py * half_w)
    msp.add_lwpolyline(
        [tip, p1, p2],
        close=True,
        dxfattribs={"layer": layer},
    )


def _linear_dim(
    msp: Any,
    p1: tuple[float, float],
    p2: tuple[float, float],
    dim_pos: float,
    *,
    horizontal: bool,
    height: float,
    arrow: float,
    layer: str,
    text_side: int = 1,
) -> None:
    """Manual dimension: extension stubs, dim line, arrows, centered text."""
    if horizontal:
        line = ((p1[0], dim_pos), (p2[0], dim_pos))
        ticks = ((p1[0], p1[1]), (p2[0], p2[1]))
        mid_y = dim_pos + (height * 0.35 if text_side > 0 else -height * 1.4)
        mid = ((p1[0] + p2[0]) / 2 - height * 0.8, mid_y)
        a1, a2 = 0.0, 180.0
    else:
        line = ((dim_pos, p1[1]), (dim_pos, p2[1]))
        ticks = ((p1[0], p1[1]), (p2[0], p2[1]))
        mid = (dim_pos + height * 0.35, (p1[1] + p2[1]) / 2 - height * 0.4)
        a1, a2 = 90.0, 270.0
    _line(msp, ticks[0], line[0], layer)
    _line(msp, ticks[1], line[1], layer)
    _line(msp, line[0], line[1], layer)
    _arrow(msp, line[0], a1, arrow, layer)
    _arrow(msp, line[1], a2, arrow, layer)
    length = p2[0] - p1[0] if horizontal else p2[1] - p1[1]
    _text(msp, _fmt(length), mid, height, layer)


def _arc_coverage(arcs: list[Any]) -> float:
    """Union of arc angle spans in degrees; ~360 means the group is a hole."""
    intervals: list[tuple[float, float]] = []
    for arc in arcs:
        start = arc.dxf.start_angle % 360.0
        end = arc.dxf.end_angle % 360.0
        if end <= start:
            end += 360.0
        intervals.append((start, end))
    intervals.sort()
    total = 0.0
    cur_start, cur_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            total += cur_end - cur_start
            cur_start, cur_end = start, end
    return total + cur_end - cur_start


def hole_circles(msp: Any) -> list[tuple[float, float, float]]:
    """(cx, cy, r) for true closed circles: CIRCLE entities, plus ARC groups
    sharing a center+radius whose combined span reaches ~360° (OCCT splits
    some holes into arc segments). Partial arcs (fillets, slot lips) are
    skipped — they are radii, not diameters.

    Shared with `dxf_lint`, which uses the same detection to check a hole
    table is present.
    """
    holes: list[tuple[float, float, float]] = []
    arc_groups: dict[tuple[float, float, float], list[Any]] = {}
    for entity in msp:
        if entity.dxftype() == "CIRCLE":
            holes.append((entity.dxf.center.x, entity.dxf.center.y, entity.dxf.radius))
        elif entity.dxftype() == "ARC":
            key = (
                round(entity.dxf.center.x, 4),
                round(entity.dxf.center.y, 4),
                round(entity.dxf.radius, 4),
            )
            arc_groups.setdefault(key, []).append(entity)
    for (cx, cy, r), arcs in arc_groups.items():
        if _arc_coverage(arcs) >= 359.0:
            holes.append((cx, cy, r))
    return sorted(holes)


def _inside(
    point: tuple[float, float],
    rect: tuple[tuple[float, float], tuple[float, float]],
) -> bool:
    (x0, y0), (x1, y1) = rect
    return x0 <= point[0] <= x1 and y0 <= point[1] <= y1


def _diameter_dims(
    msp: Any,
    holes: list[tuple[float, float, float]],
    height: float,
    arrow: float,
    layer: str,
    blocked: tuple[tuple[float, float], tuple[float, float]] | None = None,
) -> None:
    rad = math.radians(_DIAMETER_ANGLE_DEG)
    ux, uy = math.cos(rad), math.sin(rad)
    for index, (cx, cy, r) in enumerate(holes):
        # Alternate the label side so labels on neighboring holes do not
        # collide, then dodge the title block if one was provided.
        side = 1 if index % 2 == 0 else -1
        candidates = [
            (cx + side * ux * (r + height), cy + uy * (r + height)),
            (cx - side * ux * (r + height), cy + uy * (r + height)),
            (cx - side * ux * (r + height), cy - uy * (r + height)),
            (cx + side * ux * (r + height), cy - uy * (r + height)),
            (cx - side * ux * (r + 3 * height), cy + uy * (r + 3 * height)),
            (cx, cy + r + 4 * height),
            (cx + side * ux * (r + 5 * height), cy + uy * (r + 5 * height)),
        ]
        text_pos = candidates[0]
        if blocked is not None:
            for candidate in candidates:
                if not _inside(candidate, blocked):
                    text_pos = candidate
                    break
        p1 = (cx - ux * r, cy - uy * r)
        p2 = (cx + ux * r, cy + uy * r)
        _line(msp, p1, p2, layer)
        _arrow(msp, p1, math.degrees(rad) + 180, arrow, layer)
        _arrow(msp, p2, math.degrees(rad), arrow, layer)
        _text(msp, f"%%c{_fmt(2 * r)}", text_pos, height, layer)


# General-tolerance note per process — machining and sheet metal cite the
# ISO 2768 class shops expect; FDM and molding use the processes' typical
# achievable band since 2768 classes do not map onto them.
_GENERAL_TOLERANCE_NOTE: dict[str, str] = {
    "fdm": "GEN TOL ±0.3 mm",
    "machining": "GEN TOL ISO 2768-m",
    "molding": "GEN TOL ±0.2 mm",
    "sheet_metal": "GEN TOL ISO 2768-c",
}
_DEBURR_PROCESSES = {"machining", "sheet_metal"}
# Row pitch must stay above dxf_lint's text-line estimate (1.4x height) or
# stacked rows collide; the size caps below yield to this floor.
_MIN_ROW_PITCH = 1.55


def _center_mark(msp: Any, cx: float, cy: float, r: float, height: float, layer: str) -> None:
    """Crosshair center mark reaching a little past the circle edge."""
    arm = r + height * 0.8
    _line(msp, (cx - arm, cy), (cx + arm, cy), layer)
    _line(msp, (cx, cy - arm), (cx, cy + arm), layer)


def _hole_tag(hole_index: int) -> str:
    return f"A{hole_index + 1}"


def _notes_rows(
    *,
    holes: list[tuple[float, float, float]],
    datum: tuple[float, float],
    process: str | None,
    fits: list[FitDeclaration],
) -> list[str]:
    """General notes + hole table rows (top-down), all contract-derived."""
    rows: list[str] = []
    if holes:
        rows.append("HOLE TABLE")
        rows.append("HOLE  DIA   X     Y")
        for index, (cx, cy, r) in enumerate(holes):
            rows.append(
                f"{_hole_tag(index):<5} %%c{_fmt(2 * r):<5} "
                f"X{_fmt(cx - datum[0])} Y{_fmt(cy - datum[1])}"
            )
    n = 0
    rows.append("NOTES")
    n += 1
    rows.append(f"{n}. UNITS mm")
    n += 1
    rows.append(f"{n}. {_GENERAL_TOLERANCE_NOTE.get(process or '', 'GEN TOL ISO 2768-m')}")
    if holes:
        n += 1
        rows.append(f"{n}. HOLE X/Y FROM LOWER-LEFT EDGE")
    if (process or "") in _DEBURR_PROCESSES:
        n += 1
        rows.append(f"{n}. DEBURR EDGES")
    for fit in fits:
        n += 1
        rows.append(
            f"{n}. FIT {fit.id} {fit.feature} %%c{_fmt(fit.nominal_mm)} "
            f"{fit.hole_class}/{fit.shaft_class} {fit.intent}"
        )
    return rows


def _notes_block(
    msp: Any,
    rows: list[str],
    *,
    frame_min: tuple[float, float],
    frame_max: tuple[float, float],
    anchor_top: float,
    height: float,
    layer: str,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Stacked notes/hole-table block right-aligned above the title block —
    the ISO 7200 position for tables. Returns its bounding rect."""
    row_h = height * 1.6
    box_h = row_h * len(rows)
    frame_h = frame_max[1] - frame_min[1]
    if box_h > frame_h * 0.45:
        row_h = max(height * _MIN_ROW_PITCH, frame_h * 0.45 / len(rows))
        box_h = row_h * len(rows)
    text_w = height * 0.95
    box_w = (max(len(row) for row in rows) + 2) * text_w
    x0 = frame_max[0] - box_w
    y0 = anchor_top
    box_top = y0 + box_h
    corners = [
        (x0, y0),
        (frame_max[0], y0),
        (frame_max[0], box_top),
        (x0, box_top),
    ]
    msp.add_lwpolyline(corners, close=True, dxfattribs={"layer": layer})
    for i in range(1, len(rows)):
        y = y0 + i * row_h
        _line(msp, (x0, y), (frame_max[0], y), layer)
    for i, row in enumerate(rows):
        _text(
            msp,
            row,
            (x0 + height * 0.5, y0 + box_h - (i + 1) * row_h + (row_h - height) / 2),
            height,
            layer,
        )
    return (x0, y0), (frame_max[0], box_top)


def _title_block(
    msp: Any,
    frame_min: tuple[float, float],
    frame_max: tuple[float, float],
    *,
    design: str,
    part_id: str,
    material: str | None = None,
    process: str | None = None,
    height: float,
    layer: str,
) -> tuple[tuple[float, float], tuple[float, float]]:
    rows = [
        f"DESIGN  {design}",
        f"PART    {part_id}",
        *([f"MATERIAL {material}"] if material is not None else []),
        *([f"PROCESS  {process}"] if process is not None else []),
        "SCALE   1:1   UNITS mm",
        f"GENERATOR mech {__version__}",
        "FORMAT  outline (top)",
    ]
    row_h = height * 1.6
    box_h = row_h * len(rows)
    frame_h = frame_max[1] - frame_min[1]
    if box_h > frame_h * 0.28:
        row_h = max(height * _MIN_ROW_PITCH, frame_h * 0.28 / len(rows))
        box_h = row_h * len(rows)
    text_w = height * 0.95
    box_w = (max(len(row) for row in rows) + 2) * text_w
    x0 = frame_max[0] - box_w
    y0 = frame_min[1]
    box_top = y0 + box_h
    corners = [
        (x0, y0),
        (frame_max[0], y0),
        (frame_max[0], box_top),
        (x0, box_top),
    ]
    msp.add_lwpolyline(corners, close=True, dxfattribs={"layer": layer})
    for i in range(1, len(rows)):
        y = y0 + i * row_h
        _line(msp, (x0, y), (frame_max[0], y), layer)
    for i, row in enumerate(rows):
        _text(
            msp,
            row,
            (x0 + height * 0.5, y0 + box_h - (i + 1) * row_h + (row_h - height) / 2),
            height,
            layer,
        )
    return (x0, y0), (frame_max[0], box_top)


def annotate_dxf(
    path: Path,
    *,
    design: str,
    part_id: str,
    material: str | None = None,
    process: str | None = None,
    fits: list[FitDeclaration] | None = None,
) -> None:
    """Draw a frame, overall extents dimensions, hole diameters + a hole
    table, center marks, a notes block, and a title block into the DXF at
    `path`; pins volatile fields so bytes stay stable."""
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    ext = bbox.extents(msp)
    w = ext.extmax.x - ext.extmin.x
    h = ext.extmax.y - ext.extmin.y
    span = max(w, h)
    margin = span * _FRAME_MARGIN_RATIO
    height = max(span * _TEXT_HEIGHT_RATIO, _MIN_TEXT_HEIGHT_MM)
    arrow = height * 1.9

    for layer_name, color in (("FRAME", 8), ("DIMS", 1), ("TITLE", 4), ("NOTES", 3)):
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=color)

    fx0 = ext.extmin.x - margin
    fy0 = ext.extmin.y - margin
    fx1 = ext.extmax.x + margin
    fy1 = ext.extmax.y + margin

    holes = hole_circles(msp)
    notes_rows = _notes_rows(
        holes=holes,
        datum=(ext.extmin.x, ext.extmin.y),
        process=process,
        fits=fits or [],
    )
    # Right-hand documentation column: the frame widens past the part's
    # margin by exactly the notes block's width, so notes and the hole
    # table never crowd the drawing and the title block anchors the
    # column's bottom-right corner.
    notes_w = (max(len(row) for row in notes_rows) + 2) * height * 0.95
    fx1 += margin * 0.4 + notes_w
    msp.add_lwpolyline(
        [(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)],
        close=True,
        dxfattribs={"layer": "FRAME"},
    )

    _linear_dim(
        msp,
        (ext.extmin.x, ext.extmax.y),
        (ext.extmax.x, ext.extmax.y),
        fy1 - margin * 0.45,
        horizontal=True,
        height=height,
        arrow=arrow,
        layer="DIMS",
        text_side=-1,
    )
    _linear_dim(
        msp,
        (ext.extmin.x, ext.extmin.y),
        (ext.extmin.x, ext.extmax.y),
        fx0 + margin * 0.35,
        horizontal=False,
        height=height,
        arrow=arrow,
        layer="DIMS",
    )
    blocked = _title_block(
        msp,
        (fx0, fy0),
        (fx1, fy1),
        design=design,
        part_id=part_id,
        material=material,
        process=process,
        height=height,
        layer="TITLE",
    )
    # The notes/hole-table block stacks directly above the title block; its
    # footprint joins `blocked` so hole-diameter labels dodge it too.
    notes_rect = _notes_block(
        msp,
        notes_rows,
        frame_min=(fx0, fy0),
        frame_max=(fx1, fy1),
        anchor_top=blocked[1][1],
        height=height,
        layer="NOTES",
    )
    blocked = (
        (min(blocked[0][0], notes_rect[0][0]), blocked[0][1]),
        (max(blocked[1][0], notes_rect[1][0]), notes_rect[1][1]),
    )
    _diameter_dims(msp, holes, height, arrow, "DIMS", blocked)
    for index, (cx, cy, r) in enumerate(holes):
        _center_mark(msp, cx, cy, r, height, "DIMS")
        tag = _hole_tag(index)
        _text(
            msp,
            tag,
            (cx - r - height * 0.4 - len(tag) * height * 0.7, cy - height * 0.5),
            height,
            "DIMS",
        )

    doc.header["$TDCREATE"] = 0.0
    doc.header["$TDUPDATE"] = 0.0
    doc.saveas(str(path))
    text = path.read_text(encoding="utf-8", errors="replace")
    text = _EZDXF_VERSION_PATTERN.sub("1.4.4 @ 0", text)
    text = _GUID_PATTERN.sub(_NIL_GUID, text)
    path.write_text(text, encoding="utf-8")
