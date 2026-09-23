"""Bracket generator: plate, L, and U forms.

Coordinate convention: the base plate spans X and Y at Z in [0, t]. For an
L bracket the vertical leg stands on the -X end and rises to z=leg_mm; for a
U bracket a second leg stands on the +X end. Leg-face holes address the -X
leg (the only leg of an L): their x_mm is height along Z centred at leg_mm/2
and their y_mm is the Y position. Plate/base-face holes cut along Z at
(x_mm, y_mm) centred on the plate. hole.depth_mm=None means through.
"""

from __future__ import annotations

from typing import Any

from ..brief import BracketHole, BracketSpec, DesignBrief
from .common import GeneratedDesign, GeneratedPart, build123d
from .features import attach_rib, attach_snap_fit

CUT_OVER_MM = 2.0


class _BracketWallHost:
    """Map the bracket legs onto the 'left'/'right' wall convention."""

    def __init__(self, spec: BracketSpec) -> None:
        self.width_mm = spec.base_mm
        self.depth_mm = spec.width_mm
        self.wall_mm = spec.thickness_mm
        self.floor_mm = spec.thickness_mm


def _base_plate(spec: BracketSpec) -> Any:
    b = build123d()
    length = spec.plate_length_mm if spec.form == "plate" else spec.base_mm
    return b.Box(
        length,
        spec.width_mm,
        spec.thickness_mm,
        align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
    )


def _leg(spec: BracketSpec, x_outer: float) -> Any:
    """Vertical leg whose outer face sits at x_outer; leg extends inward (+X)."""
    b = build123d()
    return b.Pos(x_outer + spec.thickness_mm / 2, 0, 0) * b.Box(
        spec.thickness_mm,
        spec.width_mm,
        spec.leg_mm,
        align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
    )


def _inner_corner_fillet(spec: BracketSpec, bracket: Any) -> Any:
    if spec.inner_fillet_mm <= 0 or spec.form == "plate":
        return bracket
    b = build123d()
    inner_xs = [-spec.base_mm / 2 + spec.thickness_mm]
    if spec.form == "u":
        inner_xs.append(spec.base_mm / 2 - spec.thickness_mm)
    eps = spec.thickness_mm * 0.25

    def at_inner_corner(edge: Any) -> bool:
        c = edge.center()
        return any(abs(c.X - ix) < eps for ix in inner_xs) and abs(c.Z - spec.thickness_mm) < eps

    edges = [edge for edge in bracket.edges().filter_by(b.Axis.Y) if at_inner_corner(edge)]
    if len(edges) == 0:
        return bracket
    return b.fillet(edges, spec.inner_fillet_mm)


def _gusset(spec: BracketSpec) -> Any | None:
    """Triangular gusset on the -X inner corner (L brackets only)."""
    if not spec.gusset or spec.form != "l":
        return None
    b = build123d()
    size = min(10.0, 0.5 * (min(spec.base_mm, spec.leg_mm) - spec.thickness_mm))
    if size <= 0:
        return None
    triangle = b.Polygon(
        (0, 0),
        (size, 0),
        (0, size),
        align=(b.Align.NONE, b.Align.NONE),
    )
    solid = b.extrude(triangle, amount=spec.thickness_mm / 2, both=True)
    # Origin at the inner corner (leg inner face, base top): first sketch leg
    # runs +X along the base, second runs +Z up the leg, thickness centred on Y.
    # Shifted 0.1 mm into both faces so the union welds rather than touching
    # coplanar surfaces (tangent contacts produce a non-manifold mesh).
    return (
        b.Pos(-spec.base_mm / 2 + spec.thickness_mm - 0.1, 0, spec.thickness_mm - 0.1)
        * b.Rot(90, 0, 0)
        * solid
    )


def _hole_cutter(spec: BracketSpec, hole: BracketHole) -> Any:
    b = build123d()
    depth = hole.depth_mm or (spec.thickness_mm + CUT_OVER_MM)
    if hole.face in ("base", "plate"):
        z_center = spec.thickness_mm - depth / 2 + CUT_OVER_MM / 2
        return b.Pos(hole.x_mm, hole.y_mm, z_center) * b.Cylinder(
            radius=hole.diameter_mm / 2,
            height=depth + CUT_OVER_MM,
        )
    x_face = -spec.base_mm / 2 + spec.thickness_mm
    return b.Pos(
        x_face - depth / 2 + CUT_OVER_MM / 2,
        hole.y_mm,
        spec.leg_mm / 2 + hole.x_mm,
    ) * b.Cylinder(
        radius=hole.diameter_mm / 2,
        height=depth + CUT_OVER_MM,
        rotation=(0, -90, 0),
    )


def _countersink_cutter(spec: BracketSpec, hole: BracketHole) -> Any:
    """90-degree countersink cone cut from the outer surface inward."""
    b = build123d()
    dia = hole.countersink_diameter_mm or hole.diameter_mm * 2
    depth = dia / 2  # 90-degree included angle
    small = max(hole.diameter_mm, dia - 2 * depth)
    cone = b.Cone(bottom_radius=small / 2, top_radius=dia / 2, height=depth)
    if hole.face in ("base", "plate"):
        return b.Pos(hole.x_mm, hole.y_mm, spec.thickness_mm - depth / 2) * cone
    x_surface = -spec.base_mm / 2
    return (
        b.Pos(x_surface + depth / 2, hole.y_mm, spec.leg_mm / 2 + hole.x_mm)
        * b.Rot(0, -90, 0)
        * cone
    )


def _attach_bracket_features(brief: DesignBrief, spec: BracketSpec, bracket: Any) -> Any:
    host = _BracketWallHost(spec)
    for feature in brief.mechanism_features:
        if feature.mount not in ("base", "leg", "plate"):
            continue
        if feature.type == "rib":
            bracket += attach_rib(feature, host)
        elif feature.type == "snap_fit":
            bracket += attach_snap_fit(feature, host)
    return bracket


def generate_bracket(brief: DesignBrief) -> GeneratedDesign:
    spec = brief.bracket
    if spec is None:
        raise ValueError("bracket spec is missing")
    bracket = _base_plate(spec)
    if spec.form in ("l", "u"):
        bracket += _leg(spec, -spec.base_mm / 2)
    if spec.form == "u":
        bracket += _leg(spec, spec.base_mm / 2 - spec.thickness_mm)
    gusset = _gusset(spec)
    if gusset is not None:
        bracket += gusset
    bracket = _inner_corner_fillet(spec, bracket)
    for hole in spec.holes:
        bracket -= _hole_cutter(spec, hole)
        if hole.countersink_diameter_mm is not None:
            bracket -= _countersink_cutter(spec, hole)
    bracket = _attach_bracket_features(brief, spec, bracket)
    return GeneratedDesign(
        parts=[GeneratedPart("bracket", bracket)],
        provenance={"generator": "bracket", "form": spec.form},
    )
