"""Modeled mechanism features for the enclosure shell.

Snap-fit beams, ribs, and bosses are attached to the inner shell geometry so
that gates can measure them in the kernel. Living hinges and detents are
parametric-only (checked by rules, not modeled).

Inner side-wall features use a local frame where +X points into the cavity,
+Y runs tangentially along the wall, and +Z is up. The rotation angles below
map that frame onto each wall.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..brief import MechanismFeature
from .common import build123d

_WALL_ANGLE = {
    "left": 0.0,
    "right": 180.0,
    "front": 90.0,
    "back": -90.0,
}

# Features weld into their host face by this depth; a coplanar contact
# produces a non-manifold mesh on export.
_WELD_MM = 0.1


class WallHost(Protocol):
    """Structural fields feature placement needs from the host part."""

    width_mm: float
    depth_mm: float
    wall_mm: float
    floor_mm: float


def _wall_location(feature: MechanismFeature, host: WallHost) -> Any:
    """Location on the inner wall face: origin at attach point, +X into cavity."""
    b = build123d()
    if feature.face in ("front", "back"):
        x = feature.x_mm
        y = (
            -(host.depth_mm / 2 - host.wall_mm)
            if feature.face == "front"
            else host.depth_mm / 2 - host.wall_mm
        )
    else:
        x = (
            -(host.width_mm / 2 - host.wall_mm)
            if feature.face == "left"
            else host.width_mm / 2 - host.wall_mm
        )
        y = feature.x_mm
    z = host.floor_mm + feature.z_mm
    return b.Pos(x, y, z) * b.Rot(0, 0, _WALL_ANGLE[feature.face])


def attach_snap_fit(feature: MechanismFeature, spec: WallHost) -> Any:
    """Cantilever snap beam on the inner wall, hook at the free end.

    x_mm is the tangential position along the wall, z_mm the beam root height
    above the floor top face. The hook protrudes toward the wall by
    deflection_mm — the interference the catch must clear on assembly.
    """
    b = build123d()
    t = feature.hook_thickness_mm
    w = feature.width_mm
    length = feature.length_mm
    hook_l = min(0.2 * length, 1.5 * t)
    loc = _wall_location(feature, spec)
    beam = loc * b.Pos(t / 2 - _WELD_MM, 0, length / 2) * b.Box(t, w, length)
    hook = (
        loc
        * b.Pos(
            (t - feature.deflection_mm) / 2 - _WELD_MM,
            0,
            length - hook_l / 2,
        )
        * b.Box(t + feature.deflection_mm, w, hook_l)
    )
    return beam + hook


def attach_rib(feature: MechanismFeature, spec: WallHost) -> Any:
    """Triangular gusset: height_mm up the wall, length_mm into the cavity."""
    b = build123d()
    loc = _wall_location(feature, spec)
    triangle = b.Polygon(
        (-_WELD_MM, 0),
        (feature.length_mm, 0),
        (-_WELD_MM, feature.height_mm),
        align=(b.Align.NONE, b.Align.NONE),
    )
    return loc * b.extrude(
        b.Rot(90, 0, 0) * triangle,
        amount=feature.thickness_mm / 2,
        both=True,
    )


def attach_boss(feature: MechanismFeature, spec: WallHost) -> Any:
    """Boss on the floor top face at (x_mm, y_mm), id hole blind."""
    b = build123d()
    h = feature.height_mm or feature.od_mm
    boss = b.Pos(feature.x_mm, feature.y_mm, spec.floor_mm - _WELD_MM) * b.Cylinder(
        radius=feature.od_mm / 2,
        height=h + _WELD_MM,
        align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
    )
    boss -= b.Pos(feature.x_mm, feature.y_mm, spec.floor_mm - _WELD_MM) * b.Cylinder(
        radius=feature.id_mm / 2,
        height=h + _WELD_MM + 0.1,
        align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
    )
    return boss
