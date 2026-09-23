"""Deterministic design rules for opt-in mechanism features.

Formulas follow standard cantilever snap-fit and living-hinge design rules.
A finding is a verdict datum, not advice: pass/fail/unknown and measured
values only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .brief import DesignBrief, MechanismFeature
from .standards import PROCESS_LIMITS, MaterialSpec, ProcessLimits

RuleStatus = Literal["pass", "fail", "unknown"]

VALID_MOUNTS: dict[str, tuple[str, ...]] = {
    "enclosure": ("shell", "lid"),
    "bracket": ("base", "leg", "plate"),
    "spur_gear": (),
}


@dataclass(frozen=True)
class MechanismFinding:
    feature_id: str
    feature_type: str
    rule_id: str
    status: RuleStatus
    message: str
    measured: float | None = None
    limit: float | None = None


def _finding(
    feature: MechanismFeature,
    rule_id: str,
    status: RuleStatus,
    message: str,
    measured: float | None = None,
    limit: float | None = None,
) -> MechanismFinding:
    return MechanismFinding(
        feature_id=feature.id,
        feature_type=feature.type,
        rule_id=rule_id,
        status=status,
        message=message,
        measured=measured,
        limit=limit,
    )


def check_mechanism_features(brief: DesignBrief) -> list[MechanismFinding]:
    """Rule checks on every declared mechanism feature."""
    material_key = brief.material.upper()
    from .standards import MATERIALS

    material = MATERIALS[material_key]
    limits = PROCESS_LIMITS[brief.process]
    findings: list[MechanismFinding] = []
    for feature in brief.mechanism_features:
        if feature.mount not in VALID_MOUNTS[brief.design_type]:
            findings.append(
                _finding(
                    feature,
                    "mount",
                    "fail",
                    f"mount '{feature.mount}' is not valid for {brief.design_type}",
                )
            )
            continue
        findings.extend(_check_feature(feature, material, limits, brief))
    return findings


def _check_feature(
    feature: MechanismFeature,
    material: MaterialSpec,
    limits: ProcessLimits,
    brief: DesignBrief,
) -> list[MechanismFinding]:
    if feature.type == "snap_fit":
        return _check_snap_fit(feature, material)
    if feature.type == "living_hinge":
        return _check_living_hinge(feature, material)
    if feature.type == "rib":
        return _check_rib(feature, limits, brief)
    if feature.type == "boss":
        return _check_boss(feature, limits)
    return _check_detent(feature)


def _check_snap_fit(feature: MechanismFeature, material: MaterialSpec) -> list[MechanismFinding]:
    # Cantilever snap fit, constant cross-section: strain at the fixed end
    # is epsilon = 1.5 * t * deflection / L^2.
    if feature.length_mm <= 0 or feature.hook_thickness_mm <= 0:
        return [
            _finding(
                feature,
                "snap_fit_params",
                "fail",
                "snap_fit requires length_mm and hook_thickness_mm",
            )
        ]
    strain = 1.5 * feature.hook_thickness_mm * feature.deflection_mm / (feature.length_mm**2)
    status: RuleStatus = "pass" if strain <= material.allowable_strain else "fail"
    findings = [
        _finding(
            feature,
            "snap_fit_strain",
            status,
            "cantilever root strain against the material allowable strain",
            measured=round(strain, 5),
            limit=material.allowable_strain,
        )
    ]
    aspect = feature.length_mm / feature.hook_thickness_mm
    findings.append(
        _finding(
            feature,
            "snap_fit_aspect",
            "pass" if aspect >= 5.0 else "fail",
            "beam length-to-thickness aspect ratio (>= 5 for the formula to hold)",
            measured=round(aspect, 3),
            limit=5.0,
        )
    )
    return findings


def _check_living_hinge(
    feature: MechanismFeature, material: MaterialSpec
) -> list[MechanismFinding]:
    if feature.web_thickness_mm <= 0:
        return [
            _finding(
                feature, "living_hinge_params", "fail", "living_hinge requires web_thickness_mm"
            )
        ]
    if material.living_hinge_max_mm is None:
        return [
            _finding(
                feature,
                "living_hinge_material",
                "fail",
                f"material {material.key} is not living-hinge capable",
            )
        ]
    limit = material.living_hinge_max_mm
    status: RuleStatus = "pass" if feature.web_thickness_mm <= limit else "fail"
    return [
        _finding(
            feature,
            "living_hinge_web",
            status,
            "web thickness against the material living-hinge maximum",
            measured=feature.web_thickness_mm,
            limit=limit,
        )
    ]


def _check_rib(
    feature: MechanismFeature, limits: ProcessLimits, brief: DesignBrief
) -> list[MechanismFinding]:
    if feature.height_mm <= 0 or feature.length_mm <= 0:
        return [_finding(feature, "rib_params", "fail", "rib requires height_mm and length_mm")]
    if feature.thickness_mm <= 0:
        return [_finding(feature, "rib_thickness", "fail", "rib requires thickness_mm")]
    wall = _host_wall_mm(brief)
    if wall is None:
        return [_finding(feature, "rib_wall", "unknown", "host wall thickness is unknown")]
    limit = limits.rib_wall_ratio_max * wall
    status: RuleStatus = "pass" if feature.thickness_mm <= limit else "fail"
    return [
        _finding(
            feature,
            "rib_wall_ratio",
            status,
            "rib thickness as a fraction of the adjacent wall (sink rule)",
            measured=feature.thickness_mm,
            limit=round(limit, 3),
        )
    ]


def _check_boss(feature: MechanismFeature, limits: ProcessLimits) -> list[MechanismFinding]:
    if feature.od_mm <= 0 or feature.id_mm <= 0:
        return [_finding(feature, "boss_params", "fail", "boss requires od_mm and id_mm")]
    ratio = feature.od_mm / feature.id_mm
    findings = [
        _finding(
            feature,
            "boss_od_ratio",
            "pass" if ratio >= 2.0 else "fail",
            "boss outer-to-inner diameter ratio (>= 2 for screw bosses)",
            measured=round(ratio, 3),
            limit=2.0,
        )
    ]
    wall = (feature.od_mm - feature.id_mm) / 2
    findings.append(
        _finding(
            feature,
            "boss_min_wall",
            "pass" if wall >= limits.min_wall_mm else "fail",
            "boss wall thickness against the process minimum",
            measured=round(wall, 3),
            limit=limits.min_wall_mm,
        )
    )
    return findings


def _check_detent(feature: MechanismFeature) -> list[MechanismFinding]:
    if feature.ramp_angle_deg <= 0:
        return [_finding(feature, "detent_params", "fail", "detent requires ramp_angle_deg")]
    status: RuleStatus = "pass" if feature.ramp_angle_deg <= 45.0 else "fail"
    return [
        _finding(
            feature,
            "detent_ramp",
            status,
            "detent ramp angle (<= 45 degrees to remain releasable)",
            measured=feature.ramp_angle_deg,
            limit=45.0,
        )
    ]


def _host_wall_mm(brief: DesignBrief) -> float | None:
    if brief.enclosure is not None:
        return brief.enclosure.wall_mm
    if brief.bracket is not None:
        return brief.bracket.thickness_mm
    return None


def spur_gear_min_teeth(pressure_angle_deg: float) -> int:
    """Minimum teeth for a standard full-depth profile without undercut."""
    return math.ceil(2.0 / (math.sin(math.radians(pressure_angle_deg)) ** 2))


def check_gear_rules(brief: DesignBrief) -> list[MechanismFinding]:
    """Deterministic checks on a spur-gear brief."""
    if brief.spur_gear is None:
        return []
    gear = brief.spur_gear
    findings: list[MechanismFinding] = []
    z_min = spur_gear_min_teeth(gear.pressure_angle_deg)
    findings.append(
        MechanismFinding(
            feature_id="gear",
            feature_type="spur_gear",
            rule_id="gear_undercut",
            status="pass" if gear.teeth >= z_min else "fail",
            message=(
                f"teeth {gear.teeth} against the no-undercut minimum {z_min} "
                f"for {gear.pressure_angle_deg} degrees"
            ),
            measured=float(gear.teeth),
            limit=float(z_min),
        )
    )
    if gear.backlash_mm > 0:
        limit = 0.2 * gear.module_mm
        findings.append(
            MechanismFinding(
                feature_id="gear",
                feature_type="spur_gear",
                rule_id="gear_backlash",
                status="pass" if gear.backlash_mm <= limit else "fail",
                message="declared backlash against 0.2 * module",
                measured=gear.backlash_mm,
                limit=round(limit, 4),
            )
        )
    return findings
