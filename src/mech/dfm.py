"""Deterministic manufacturing-process checks over the design brief.

Each finding carries a rule id, pass/fail/unknown status, and the measured
value against its limit. Unknown is fail-closed at the gate level.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .brief import BracketSpec, DesignBrief, face_span
from .standards import ProcessLimits, process_limits

DfmStatus = Literal["pass", "fail", "unknown"]


@dataclass(frozen=True)
class DfmFinding:
    rule_id: str
    status: DfmStatus
    message: str
    measured: float | None = None
    limit: float | None = None
    feature_id: str | None = None


def _finding(
    rule_id: str,
    status: DfmStatus,
    message: str,
    *,
    measured: float | None = None,
    limit: float | None = None,
    feature_id: str | None = None,
) -> DfmFinding:
    return DfmFinding(
        rule_id=rule_id,
        status=status,
        message=message,
        measured=measured,
        limit=limit,
        feature_id=feature_id,
    )


def _status(ok: bool) -> DfmStatus:
    return "pass" if ok else "fail"


def check_dfm(
    brief: DesignBrief,
    *,
    measured_min_wall_mm: float | None,
) -> list[DfmFinding]:
    """Run the manufacturing profile's rule table against the design."""
    limits = process_limits(brief.process)
    findings: list[DfmFinding] = []
    findings.extend(_check_wall(brief, limits, measured_min_wall_mm))
    findings.extend(_check_holes(brief, limits))
    findings.extend(_check_draft(brief, limits))
    findings.extend(_check_process_specific(brief, limits))
    return findings


def _check_wall(
    brief: DesignBrief, limits: ProcessLimits, measured_min_wall_mm: float | None
) -> list[DfmFinding]:
    declared = _declared_wall_mm(brief)
    findings = [
        _finding(
            "declared_wall",
            _status(declared is not None and declared >= limits.min_wall_mm),
            "declared wall thickness against the process minimum",
            measured=declared,
            limit=limits.min_wall_mm,
        )
    ]
    if brief.spur_gear is not None:
        # Gears have no opposing-face wall; the rim is covered by declared_wall.
        pass
    elif measured_min_wall_mm is None:
        findings.append(
            _finding(
                "measured_wall",
                "unknown",
                "measured minimum wall is unavailable",
            )
        )
    else:
        findings.append(
            _finding(
                "measured_wall",
                _status(measured_min_wall_mm >= limits.min_wall_mm),
                "measured minimum wall against the process minimum",
                measured=round(measured_min_wall_mm, 3),
                limit=limits.min_wall_mm,
            )
        )
    if limits.max_wall_mm > 0 and declared is not None:
        findings.append(
            _finding(
                "max_wall",
                _status(declared <= limits.max_wall_mm),
                "declared wall thickness against the uniform-wall maximum",
                measured=declared,
                limit=limits.max_wall_mm,
            )
        )
    return findings


def _check_holes(brief: DesignBrief, limits: ProcessLimits) -> list[DfmFinding]:
    findings: list[DfmFinding] = []
    min_diameter = limits.min_hole_diameter_mm
    thickness = _declared_wall_mm(brief)
    if brief.process == "sheet_metal" and thickness is not None:
        min_diameter = max(min_diameter, thickness)
    for hole_id, diameter in _hole_diameters(brief):
        findings.append(
            _finding(
                "min_hole_diameter",
                _status(diameter >= min_diameter),
                "hole diameter against the process minimum",
                measured=diameter,
                limit=round(min_diameter, 3),
                feature_id=hole_id,
            )
        )
    findings.extend(_check_hole_edges(brief, limits))
    return findings


def _check_hole_edges(brief: DesignBrief, limits: ProcessLimits) -> list[DfmFinding]:
    findings: list[DfmFinding] = []
    if brief.enclosure is not None:
        for opening in brief.enclosure.openings:
            face_w, face_h = face_span(brief.enclosure, opening.face)
            edge_x = face_w / 2 - abs(opening.center_x_mm) - opening.width_mm / 2
            edge_y = face_h / 2 - abs(opening.center_y_mm) - opening.height_mm / 2
            edge = min(edge_x, edge_y)
            limit = limits.hole_edge_distance_factor * min(opening.width_mm, opening.height_mm)
            findings.append(
                _finding(
                    "hole_edge_distance",
                    _status(edge >= limit),
                    "opening edge distance against the process factor",
                    measured=round(edge, 3),
                    limit=round(limit, 3),
                    feature_id=opening.id,
                )
            )
    if brief.bracket is not None:
        bracket = brief.bracket
        for hole in bracket.holes:
            span_x, span_y = _bracket_face_span(bracket, hole.face)
            edge_x = span_x / 2 - abs(hole.x_mm) - hole.diameter_mm / 2
            edge_y = span_y / 2 - abs(hole.y_mm) - hole.diameter_mm / 2
            edge = min(edge_x, edge_y)
            limit = limits.hole_edge_distance_factor * hole.diameter_mm
            findings.append(
                _finding(
                    "hole_edge_distance",
                    _status(edge >= limit),
                    "hole edge distance against the process factor",
                    measured=round(edge, 3),
                    limit=round(limit, 3),
                    feature_id=hole.id,
                )
            )
    return findings


def _check_draft(brief: DesignBrief, limits: ProcessLimits) -> list[DfmFinding]:
    if limits.min_draft_deg <= 0:
        return []
    # Our generated walls are straight; for molding the draft rule applies to
    # the declared geometry. A straight wall reports 0 draft and fails closed.
    declared_draft = 0.0
    return [
        _finding(
            "draft_angle",
            _status(declared_draft >= limits.min_draft_deg),
            "straight side walls do not satisfy the molding draft minimum",
            measured=declared_draft,
            limit=limits.min_draft_deg,
        )
    ]


def _check_process_specific(brief: DesignBrief, limits: ProcessLimits) -> list[DfmFinding]:
    findings: list[DfmFinding] = []
    if brief.process == "sheet_metal" and brief.bracket is not None:
        thickness = brief.bracket.thickness_mm
        bend_radius = brief.bracket.inner_fillet_mm
        if brief.bracket.form != "plate":
            findings.append(
                _finding(
                    "bend_radius",
                    _status(bend_radius >= limits.bend_radius_factor * thickness),
                    "inside bend radius against the process factor * thickness",
                    measured=bend_radius,
                    limit=round(limits.bend_radius_factor * thickness, 3),
                )
            )
            for hole in brief.bracket.holes:
                distance = _hole_to_bend_distance(brief.bracket, hole)
                if distance is None:
                    continue
                limit = limits.hole_to_bend_factor * thickness
                findings.append(
                    _finding(
                        "hole_to_bend",
                        _status(distance >= limit),
                        "hole centre to bend line against the process factor * thickness",
                        measured=round(distance, 3),
                        limit=round(limit, 3),
                        feature_id=hole.id,
                    )
                )
    if brief.process == "fdm" and brief.bracket is not None:
        for hole in brief.bracket.holes:
            if hole.countersink_diameter_mm is not None:
                findings.append(
                    _finding(
                        "fdm_countersink",
                        "fail",
                        "countersunk features are unsupported on fdm",
                        feature_id=hole.id,
                    )
                )
    return findings


def _declared_wall_mm(brief: DesignBrief) -> float | None:
    if brief.enclosure is not None:
        return min(brief.enclosure.wall_mm, brief.enclosure.floor_mm)
    if brief.bracket is not None:
        return brief.bracket.thickness_mm
    if brief.spur_gear is not None:
        gear = brief.spur_gear
        root_diameter_mm = gear.module_mm * (gear.teeth - 2.5)
        inner_mm = gear.hub_diameter_mm if gear.hub_diameter_mm else gear.bore_mm
        return (root_diameter_mm - inner_mm) / 2
    return None


def _hole_diameters(brief: DesignBrief) -> list[tuple[str, float]]:
    holes: list[tuple[str, float]] = []
    if brief.enclosure is not None:
        for opening in brief.enclosure.openings:
            holes.append((opening.id, min(opening.width_mm, opening.height_mm)))
        if brief.enclosure.board is not None:
            for hole in brief.enclosure.board.mount_holes:
                holes.append((hole.id, hole.diameter_mm))
    if brief.bracket is not None:
        for hole in brief.bracket.holes:
            holes.append((hole.id, hole.diameter_mm))
    if brief.spur_gear is not None:
        holes.append(("gear_bore", brief.spur_gear.bore_mm))
    return holes


def _bracket_face_span(bracket: BracketSpec, face: str) -> tuple[float, float]:
    if face == "plate":
        return bracket.plate_length_mm, bracket.width_mm
    if face == "base":
        return bracket.base_mm, bracket.width_mm
    return bracket.leg_mm, bracket.width_mm


def _hole_to_bend_distance(bracket: BracketSpec, hole: object) -> float | None:
    """Distance from a hole centre to the nearest bend line (inner corner)."""
    from .brief import BracketHole

    if not isinstance(hole, BracketHole):
        return None
    if bracket.form == "plate":
        return None
    # The inner corner is at x = -base/2 + thickness for base holes, and at
    # z = -leg/2 + thickness for leg holes, in face-local coordinates.
    if hole.face == "base":
        bend_x = -bracket.base_mm / 2 + bracket.thickness_mm
        return abs(hole.x_mm - bend_x)
    if hole.face == "leg":
        bend_y = -bracket.leg_mm / 2 + bracket.thickness_mm
        return abs(hole.y_mm - bend_y)
    return None


def check_standoff_bosses(brief: DesignBrief) -> list[DfmFinding]:
    """Declared standoff boss walls against the process minimum."""
    limits = process_limits(brief.process)
    if brief.enclosure is None or brief.enclosure.board is None:
        return []
    findings: list[DfmFinding] = []
    from .generators.enclosure import standoff_geometry

    for hole in brief.enclosure.board.mount_holes:
        od, pilot = standoff_geometry(hole.diameter_mm)
        wall = (od - pilot) / 2
        findings.append(
            _finding(
                "standoff_boss_wall",
                _status(wall >= limits.min_wall_mm),
                "standoff boss wall against the process minimum",
                measured=round(wall, 3),
                limit=limits.min_wall_mm,
                feature_id=hole.id,
            )
        )
    return findings
