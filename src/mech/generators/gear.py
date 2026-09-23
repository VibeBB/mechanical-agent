"""Metric involute spur gear generator (ISO 53 profile).

The gear axis is Z, the blank spans z in [0, thickness]. The tooth profile is
an involute of the base circle sampled between the root and tip circles,
mirrored for the two flanks, with radial segments down to the root circle.
backlash_mm thins each tooth circumferentially by that amount on the pitch
circle (half per flank) — a standard simple backlash model.
"""

from __future__ import annotations

import math
from typing import Any

from ..brief import DesignBrief, SpurGearSpec
from .common import GeneratedDesign, GeneratedPart, build123d

_INVOLUTE_STEPS = 12
_ROOT_CLEARANCE = 1.25  # dedendum factor (standard full-depth tooth)


def _involute_points(
    base_radius: float,
    r_min: float,
    r_max: float,
    steps: int = _INVOLUTE_STEPS,
) -> list[tuple[float, float]]:
    """Points (x, y) on an involute starting at angle 0 on the base circle.

    The first point is moved out to r_min on the flank's radial line so the
    profile covers [r_min, r_max].
    """
    t_max = math.sqrt(max(r_max / base_radius, 1.0) ** 2 - 1.0)
    t_min = math.sqrt(max(r_min / base_radius, 1.0) ** 2 - 1.0)
    pts: list[tuple[float, float]] = []
    for i in range(steps + 1):
        t = t_min + (t_max - t_min) * i / steps
        x = base_radius * (math.cos(t) + t * math.sin(t))
        y = base_radius * (math.sin(t) - t * math.cos(t))
        pts.append((x, y))
    return pts


def _rotate(point: tuple[float, float], angle: float) -> tuple[float, float]:
    c = math.cos(angle)
    s = math.sin(angle)
    return (point[0] * c - point[1] * s, point[0] * s + point[1] * c)


def _tooth_profile(spec: SpurGearSpec) -> list[tuple[float, float]]:
    """Closed 2D outline of one tooth, centred at angle 0 (top land on +X)."""
    m = spec.module_mm
    z = spec.teeth
    alpha = math.radians(spec.pressure_angle_deg)
    pitch_r = m * z / 2
    base_r = pitch_r * math.cos(alpha)
    tip_r = pitch_r + m
    root_r = max(pitch_r - _ROOT_CLEARANCE * m, 0.1)
    flank_r = max(root_r, base_r)

    half_tooth = math.pi / (2 * z)  # half angular tooth thickness at pitch
    inv_alpha = math.tan(alpha) - alpha
    backlash_shift = spec.backlash_mm / (2 * pitch_r) if pitch_r > 0 else 0.0
    # Rotate the base involute once so it crosses the pitch circle at
    # -(half_tooth + backlash shift); the left flank is its mirror.
    delta = -(half_tooth + backlash_shift) - inv_alpha
    right = [_rotate(p, delta) for p in _involute_points(base_r, flank_r, tip_r)]
    left = [(x, -y) for x, y in reversed(right)]

    # Radial drop from the flank start down to the root circle.
    a0 = math.atan2(right[0][1], right[0][0])
    a1 = math.atan2(left[-1][1], left[-1][0])
    pts: list[tuple[float, float]] = [(root_r * math.cos(a0), root_r * math.sin(a0))]
    pts.extend(right)
    pts.append((tip_r, 0.0))  # top-land midpoint on the tip circle
    pts.extend(left)
    pts.append((root_r * math.cos(a1), root_r * math.sin(a1)))
    # The closing segment between the last and first root points lies on a
    # chord inside the root circle — acceptable approximation of the root arc.
    return pts


def _gear_solid(spec: SpurGearSpec) -> Any:
    b = build123d()
    m = spec.module_mm
    z = spec.teeth
    pitch_r = m * z / 2
    root_r = max(pitch_r - _ROOT_CLEARANCE * m, 0.1)

    body = b.Cylinder(
        radius=root_r,
        height=spec.thickness_mm,
        align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
    )
    tooth_pts = _tooth_profile(spec)
    tooth = b.extrude(
        b.Pos(0, 0, 0) * b.Polygon(*tooth_pts, align=(b.Align.NONE, b.Align.NONE)),
        amount=spec.thickness_mm,
    )
    gear = body
    for i in range(z):
        gear += b.Pos(0, 0, 0) * b.Rot(0, 0, math.degrees(2 * math.pi * i / z)) * tooth
    gear -= b.Cylinder(
        radius=spec.bore_mm / 2,
        height=spec.thickness_mm + 2.0,
        align=(b.Align.CENTER, b.Align.CENTER, b.Align.CENTER),
    )
    if spec.hub_diameter_mm > 0 and spec.hub_height_mm > 0:
        hub = b.Cylinder(
            radius=spec.hub_diameter_mm / 2,
            height=spec.hub_height_mm,
            align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN),
        )
        hub -= b.Cylinder(
            radius=spec.bore_mm / 2,
            height=spec.hub_height_mm + 2.0,
        )
        gear += hub
    return gear


def generate_spur_gear(brief: DesignBrief) -> GeneratedDesign:
    spec = brief.spur_gear
    if spec is None:
        raise ValueError("spur_gear spec is missing")
    gear = _gear_solid(spec)
    return GeneratedDesign(
        parts=[GeneratedPart("gear", gear)],
        provenance={
            "generator": "spur_gear",
            "module_mm": spec.module_mm,
            "teeth": spec.teeth,
            "pressure_angle_deg": spec.pressure_angle_deg,
        },
    )
