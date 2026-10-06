"""Test-design suite for the deterministic mechanical rules.

Applies the techniques in docs/test-coverage.md to the rule tables that feed
the gates: 3-value boundaries (below/on/above, ``math.nextafter`` for floats)
on every numeric limit, equivalence classes over the ISO 286 nominal bins,
decision tables for the fit classification and process-specific rules, and
fail-closed negative cases for inputs the tables do not cover.
"""

from __future__ import annotations

import copy
import itertools
import math
from typing import Any

import pytest

from mech.brief import DesignBrief, FitDeclaration, StackupChain
from mech.dfm import DfmFinding, check_dfm
from mech.fits import (
    HOLE_CLASSES,
    IT_GRADES,
    NOMINAL_BINS,
    SHAFT_CLASSES,
    SHAFT_GRADES,
    _bin_index,  # pyright: ignore[reportPrivateUsage]
    evaluate_fit,
    hole_limits,
    shaft_limits,
)
from mech.mechanism import (
    MechanismFinding,
    check_gear_rules,
    check_mechanism_features,
    spur_gear_min_teeth,
)
from mech.stackup import evaluate_chain
from mech.standards import process_limits

UP = math.inf
DOWN = -math.inf


# ---------------------------------------------------------------- ISO 286 bins


@pytest.mark.parametrize("index", range(len(NOMINAL_BINS)))
def test_nominal_bin_edges_are_lower_open_upper_closed(index: int) -> None:
    lower, upper = NOMINAL_BINS[index]
    assert _bin_index(upper) == index
    assert _bin_index(math.nextafter(upper, DOWN)) == index
    assert _bin_index(math.nextafter(lower, UP)) == index
    above = _bin_index(math.nextafter(upper, UP))
    assert above == (index + 1 if index + 1 < len(NOMINAL_BINS) else None)


@pytest.mark.parametrize("nominal", [-1.0, math.nextafter(0.0, DOWN), 0.0])
def test_non_positive_nominal_has_no_bin(nominal: float) -> None:
    assert _bin_index(nominal) is None


def test_nominal_above_table_has_no_bin() -> None:
    top = NOMINAL_BINS[-1][1]
    assert _bin_index(top) == len(NOMINAL_BINS) - 1
    assert _bin_index(math.nextafter(top, UP)) is None
    assert evaluate_fit(math.nextafter(top, UP), "H7", "g6", "clearance").status == "unknown"


def test_bins_tile_the_range_without_gaps() -> None:
    for (_, upper), (lower, _) in itertools.pairwise(NOMINAL_BINS):
        assert upper == lower


@pytest.mark.parametrize(
    "hole_class",
    ["", "H", "H77", "h7", "G7", "Hx", "H9", "H5"],
)
def test_unsupported_hole_class_is_unknown(hole_class: str) -> None:
    assert hole_limits(hole_class, 20.0) is None
    assert evaluate_fit(20.0, hole_class, "g6", "clearance").status == "unknown"


@pytest.mark.parametrize("hole_class", HOLE_CLASSES)
def test_supported_hole_classes_are_hole_basis(hole_class: str) -> None:
    grade = int(hole_class[1:])
    for index, (_, upper) in enumerate(NOMINAL_BINS):
        limits = hole_limits(hole_class, upper)
        assert limits is not None
        assert limits.lower_mm == 0.0
        assert limits.upper_mm == IT_GRADES[grade][index] / 1000.0


def test_every_hole_class_the_brief_accepts_is_evaluable() -> None:
    # FitDeclaration's pattern admits H10/H11; the evaluator must cover every
    # class the schema accepts, or a valid brief fails as unknown.
    pattern = FitDeclaration.model_fields["hole_class"].metadata
    accepted = {f"H{grade}" for grade in (6, 7, 8, 10, 11)}
    assert any("10|11" in str(item) for item in pattern)
    assert accepted == set(HOLE_CLASSES)
    for hole_class in sorted(accepted):
        assert evaluate_fit(20.0, hole_class, "h6", "clearance").status == "known"
    assert evaluate_fit(20.0, "H11", "h6", "clearance").max_clearance_mm == pytest.approx(0.143)


@pytest.mark.parametrize("shaft_class", SHAFT_CLASSES)
def test_every_shaft_class_band_width_equals_its_it_grade(shaft_class: str) -> None:
    grade = SHAFT_GRADES[shaft_class]
    for index, (_, upper) in enumerate(NOMINAL_BINS):
        limits = shaft_limits(shaft_class, upper)
        assert limits is not None
        assert limits.upper_mm > limits.lower_mm
        assert limits.upper_mm - limits.lower_mm == pytest.approx(IT_GRADES[grade][index] / 1000.0)


@pytest.mark.parametrize(
    ("shaft_class", "sign"),
    [
        ("e8", "below"),
        ("f7", "below"),
        ("g6", "below"),
        ("h6", "touch"),
        ("n6", "above"),
        ("p6", "above"),
        ("s6", "above"),
    ],
)
def test_shaft_deviation_families(shaft_class: str, sign: str) -> None:
    limits = shaft_limits(shaft_class, 20.0)
    assert limits is not None
    if sign == "below":
        assert limits.upper_mm < 0
    elif sign == "touch":
        assert limits.upper_mm == 0.0
    else:
        assert limits.lower_mm > 0


@pytest.mark.parametrize("shaft_class", ["", "g", "g7", "x6", "G6"])
def test_unsupported_shaft_class_is_unknown(shaft_class: str) -> None:
    assert shaft_limits(shaft_class, 20.0) is None
    assert evaluate_fit(20.0, "H7", shaft_class, "clearance").status == "unknown"


def test_k6_lower_deviation_zero_in_first_bin() -> None:
    limits = shaft_limits("k6", 3.0)
    assert limits is not None
    assert limits.lower_mm == 0.0


# Decision table: min_clearance > 0 -> clearance; elif max_clearance < 0 ->
# interference; else transition. H7/h6 has min clearance exactly 0 (on the
# boundary), so it must classify as transition, not clearance.
@pytest.mark.parametrize(
    ("shaft_class", "classification"),
    [
        ("e8", "clearance"),
        ("f7", "clearance"),
        ("g6", "clearance"),
        ("h6", "transition"),
        ("k6", "transition"),
        ("n6", "transition"),
        ("p6", "interference"),
        ("s6", "interference"),
    ],
)
def test_fit_classification_decision_table(shaft_class: str, classification: str) -> None:
    result = evaluate_fit(20.0, "H7", shaft_class, "clearance")
    assert result.status == "known"
    assert result.classification == classification
    assert (result.reason == "") == (classification == "clearance")


def test_h7_h6_sits_on_the_zero_clearance_boundary() -> None:
    result = evaluate_fit(20.0, "H7", "h6", "transition")
    assert result.min_clearance_mm == 0.0
    assert result.max_clearance_mm > 0
    assert result.reason == ""


def test_n6_in_first_bin_touches_the_interference_boundary() -> None:
    # H7 upper 10 µm, n6 lower 4 µm: max clearance stays positive (transition).
    result = evaluate_fit(2.0, "H7", "n6", "transition")
    assert result.max_clearance_mm == pytest.approx(0.006)
    assert result.classification == "transition"


@pytest.mark.parametrize("intent", ["clearance", "transition", "interference"])
def test_unknown_fit_never_matches_an_intent(intent: Any) -> None:
    result = evaluate_fit(0.0, "H7", "g6", intent)
    assert result.status == "unknown"
    assert result.reason


# ----------------------------------------------------------------- stack-up


def _chain(min_mm: float, max_mm: float, plus: float, minus: float) -> StackupChain:
    return StackupChain.model_validate(
        {
            "id": "SC1",
            "min_mm": min_mm,
            "max_mm": max_mm,
            "elements": [{"name": "a", "nominal_mm": 2.0, "plus_mm": plus, "minus_mm": minus}],
        }
    )


@pytest.mark.parametrize(
    ("min_mm", "status"),
    [(math.nextafter(1.5, DOWN), "pass"), (1.5, "pass"), (math.nextafter(1.5, UP), "fail")],
)
def test_stackup_worst_min_boundary(min_mm: float, status: str) -> None:
    assert evaluate_chain(_chain(min_mm, 3.0, 0.0, 0.5)).status == status


@pytest.mark.parametrize(
    ("max_mm", "status"),
    [(math.nextafter(2.5, DOWN), "fail"), (2.5, "pass"), (math.nextafter(2.5, UP), "pass")],
)
def test_stackup_worst_max_boundary(max_mm: float, status: str) -> None:
    assert evaluate_chain(_chain(0.0, max_mm, 0.5, 0.0)).status == status


def test_stackup_both_violations_are_reported() -> None:
    result = evaluate_chain(_chain(1.9, 2.1, 0.5, 0.5))
    assert result.status == "fail"
    assert len(result.reasons) == 2


def test_stackup_zero_tolerance_has_zero_rss() -> None:
    result = evaluate_chain(_chain(1.0, 3.0, 0.0, 0.0))
    assert result.rss_mm == 0.0
    assert result.worst_min_mm == result.worst_max_mm == 2.0


@pytest.mark.parametrize(("min_mm", "max_mm"), [(2.0, 2.0), (2.1, 2.0)])
def test_stackup_window_must_be_non_empty(min_mm: float, max_mm: float) -> None:
    with pytest.raises(ValueError, match="min_mm"):
        _chain(min_mm, max_mm, 0.1, 0.1)


# ---------------------------------------------------------------------- DFM


def _findings(
    brief_dict: dict[str, Any], rule: str, measured: float | None = 2.0
) -> list[DfmFinding]:
    brief = DesignBrief.model_validate(brief_dict)
    return [f for f in check_dfm(brief, measured_min_wall_mm=measured) if f.rule_id == rule]


def _enclosure(base: dict[str, Any], process: str, wall: float) -> dict[str, Any]:
    data = copy.deepcopy(base)
    data["process"] = process
    data["enclosure"]["wall_mm"] = wall
    data["enclosure"]["floor_mm"] = wall
    return data


@pytest.mark.parametrize("process", ["fdm", "machining", "molding"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_declared_wall_three_value_boundary(
    enclosure_brief_dict: dict[str, Any], process: str, offset: int
) -> None:
    limit = process_limits(process).min_wall_mm
    wall = limit if offset == 0 else math.nextafter(limit, UP if offset > 0 else DOWN)
    [finding] = _findings(_enclosure(enclosure_brief_dict, process, wall), "declared_wall")
    assert finding.status == ("fail" if offset < 0 else "pass")
    assert finding.limit == limit


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_measured_wall_three_value_boundary(
    enclosure_brief_dict: dict[str, Any], offset: int
) -> None:
    limit = process_limits("fdm").min_wall_mm
    measured = limit if offset == 0 else limit + offset * 0.001
    [finding] = _findings(enclosure_brief_dict, "measured_wall", measured)
    assert finding.status == ("fail" if offset < 0 else "pass")


def test_unmeasured_wall_is_unknown(enclosure_brief_dict: dict[str, Any]) -> None:
    [finding] = _findings(enclosure_brief_dict, "measured_wall", None)
    assert finding.status == "unknown"


def test_gear_has_no_measured_wall_finding(gear_brief_dict: dict[str, Any]) -> None:
    assert _findings(gear_brief_dict, "measured_wall", None) == []


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_molding_max_wall_three_value_boundary(
    enclosure_brief_dict: dict[str, Any], offset: int
) -> None:
    limit = process_limits("molding").max_wall_mm
    wall = limit if offset == 0 else math.nextafter(limit, UP if offset > 0 else DOWN)
    [finding] = _findings(_enclosure(enclosure_brief_dict, "molding", wall), "max_wall")
    assert finding.status == ("fail" if offset > 0 else "pass")


@pytest.mark.parametrize("process", ["fdm", "machining"])
def test_max_wall_disabled_when_limit_is_zero(
    enclosure_brief_dict: dict[str, Any], process: str
) -> None:
    assert _findings(_enclosure(enclosure_brief_dict, process, 5.0), "max_wall") == []


def test_molding_straight_walls_fail_draft(enclosure_brief_dict: dict[str, Any]) -> None:
    [finding] = _findings(_enclosure(enclosure_brief_dict, "molding", 2.0), "draft_angle")
    assert finding.status == "fail"
    assert finding.limit == process_limits("molding").min_draft_deg


@pytest.mark.parametrize("process", ["fdm", "machining"])
def test_no_draft_rule_without_a_draft_minimum(
    enclosure_brief_dict: dict[str, Any], process: str
) -> None:
    assert _findings(_enclosure(enclosure_brief_dict, process, 2.0), "draft_angle") == []


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_min_hole_diameter_three_value_boundary(
    bracket_brief_dict: dict[str, Any], offset: int
) -> None:
    data = copy.deepcopy(bracket_brief_dict)
    data["process"] = "fdm"
    limit = process_limits("fdm").min_hole_diameter_mm
    diameter = limit if offset == 0 else math.nextafter(limit, UP if offset > 0 else DOWN)
    data["bracket"]["holes"] = [
        {"id": "H1", "face": "base", "x_mm": 10, "y_mm": 0, "diameter_mm": diameter}
    ]
    [finding] = _findings(data, "min_hole_diameter")
    assert finding.status == ("fail" if offset < 0 else "pass")


@pytest.mark.parametrize(("diameter", "status"), [(2.9, "fail"), (3.0, "pass"), (3.1, "pass")])
def test_sheet_metal_hole_minimum_is_the_thickness(
    bracket_brief_dict: dict[str, Any], diameter: float, status: str
) -> None:
    data = copy.deepcopy(bracket_brief_dict)
    data["process"] = "sheet_metal"
    data["bracket"]["holes"] = [
        {"id": "H1", "face": "base", "x_mm": 15, "y_mm": 0, "diameter_mm": diameter}
    ]
    [finding] = _findings(data, "min_hole_diameter")
    assert finding.limit == 3.0
    assert finding.status == status


def _bracket_edge(base: dict[str, Any], x_mm: float) -> list[DfmFinding]:
    data = copy.deepcopy(base)
    data["bracket"]["holes"] = [
        {"id": "H1", "face": "base", "x_mm": x_mm, "y_mm": 0, "diameter_mm": 5}
    ]
    return _findings(data, "hole_edge_distance")


# Machining factor 1.0, base 60 mm, diameter 5: edge = 30 - |x| - 2.5 >= 5,
# so |x| = 22.5 is on the boundary.
@pytest.mark.parametrize(
    ("x_mm", "status"),
    [(22.4, "pass"), (22.5, "pass"), (22.6, "fail"), (-22.6, "fail")],
)
def test_bracket_hole_edge_distance_boundary(
    bracket_brief_dict: dict[str, Any], x_mm: float, status: str
) -> None:
    [finding] = _bracket_edge(bracket_brief_dict, x_mm)
    assert finding.limit == 5.0
    assert finding.status == status


# Molding factor 1.5 on a 12x6 opening: limit 9 mm. Front face height 30 mm,
# so the vertical edge is 15 - |y| - 3 and |y| = 3 is on the boundary.
@pytest.mark.parametrize(("y_mm", "status"), [(2.9, "pass"), (3.0, "pass"), (3.1, "fail")])
def test_opening_edge_distance_boundary(
    enclosure_brief_dict: dict[str, Any], y_mm: float, status: str
) -> None:
    data = _enclosure(enclosure_brief_dict, "molding", 2.0)
    data["enclosure"]["openings"][0]["center_y_mm"] = y_mm
    [finding] = _findings(data, "hole_edge_distance")
    assert finding.limit == 9.0
    assert finding.status == status


def _sheet_bracket(base: dict[str, Any], **changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(base)
    data["process"] = "sheet_metal"
    data["bracket"].update(changes)
    return data


@pytest.mark.parametrize(("radius", "status"), [(2.9, "fail"), (3.0, "pass"), (3.1, "pass")])
def test_bend_radius_three_value_boundary(
    bracket_brief_dict: dict[str, Any], radius: float, status: str
) -> None:
    [finding] = _findings(_sheet_bracket(bracket_brief_dict, inner_fillet_mm=radius), "bend_radius")
    assert finding.limit == 3.0
    assert finding.status == status


# Base bend line at x = -30 + 3 = -27; limit 2.5 * 3 = 7.5, so x = -19.5 is on
# the boundary. Leg bend line at y = -20 + 3 = -17; y = -9.5 is on it.
@pytest.mark.parametrize(
    ("face", "x_mm", "y_mm", "status"),
    [
        ("base", -19.6, 0.0, "fail"),
        ("base", -19.5, 0.0, "pass"),
        ("base", -19.4, 0.0, "pass"),
        ("leg", 0.0, -9.6, "fail"),
        ("leg", 0.0, -9.5, "pass"),
        ("leg", 0.0, -9.4, "pass"),
    ],
)
def test_hole_to_bend_three_value_boundary(
    bracket_brief_dict: dict[str, Any], face: str, x_mm: float, y_mm: float, status: str
) -> None:
    hole = {"id": "H1", "face": face, "x_mm": x_mm, "y_mm": y_mm, "diameter_mm": 3}
    data = _sheet_bracket(bracket_brief_dict, inner_fillet_mm=3.0, holes=[hole])
    [finding] = _findings(data, "hole_to_bend")
    assert finding.limit == 7.5
    assert finding.status == status


# Decision table for the process-specific rules: process x bracket form.
@pytest.mark.parametrize(
    ("process", "form", "bend_rules"),
    [
        ("sheet_metal", "l", True),
        ("sheet_metal", "u", True),
        ("sheet_metal", "plate", False),
        ("machining", "l", False),
        ("fdm", "l", False),
    ],
)
def test_bend_rules_apply_only_to_formed_sheet_metal(
    bracket_brief_dict: dict[str, Any], process: str, form: str, bend_rules: bool
) -> None:
    data = copy.deepcopy(bracket_brief_dict)
    data["process"] = process
    data["bracket"]["form"] = form
    data["bracket"]["inner_fillet_mm"] = 3.0
    data["bracket"]["gusset"] = form == "l"
    if form == "plate":
        data["bracket"]["plate_length_mm"] = 60
        for hole in data["bracket"]["holes"]:
            hole["face"] = "plate"
    brief = DesignBrief.model_validate(data)
    rules = {f.rule_id for f in check_dfm(brief, measured_min_wall_mm=3.0)}
    assert ("bend_radius" in rules) is bend_rules
    assert ("hole_to_bend" in rules) is bend_rules


@pytest.mark.parametrize(
    ("process", "countersink", "expected"),
    [("fdm", 8.0, ["fail"]), ("fdm", None, []), ("machining", 8.0, [])],
)
def test_fdm_countersink_decision_table(
    bracket_brief_dict: dict[str, Any], process: str, countersink: float | None, expected: list[str]
) -> None:
    data = copy.deepcopy(bracket_brief_dict)
    data["process"] = process
    data["bracket"]["holes"][0]["countersink_diameter_mm"] = countersink
    assert [f.status for f in _findings(data, "fdm_countersink", 3.0)] == expected


# ---------------------------------------------------------------- mechanism


def _feature_findings(
    base: dict[str, Any], material: str, **feature: Any
) -> list[MechanismFinding]:
    data = copy.deepcopy(base)
    data["material"] = material
    data["mechanism_features"] = [{"id": "F1", "mount": "shell", "z_mm": 8, **feature}]
    return check_mechanism_features(DesignBrief.model_validate(data))


def _rule(findings: list[MechanismFinding], rule: str) -> str:
    [finding] = [f for f in findings if f.rule_id == rule]
    return finding.status


# ABS allowable strain 0.03; strain = 1.5 * t * d / L^2 = 0.015 * d for t=1, L=10.
@pytest.mark.parametrize(("deflection", "status"), [(1.99, "pass"), (2.0, "pass"), (2.01, "fail")])
def test_snap_fit_strain_three_value_boundary(
    enclosure_brief_dict: dict[str, Any], deflection: float, status: str
) -> None:
    findings = _feature_findings(
        enclosure_brief_dict,
        "ABS",
        type="snap_fit",
        face="left",
        length_mm=10,
        width_mm=5,
        hook_thickness_mm=1,
        deflection_mm=deflection,
    )
    assert _rule(findings, "snap_fit_strain") == status


@pytest.mark.parametrize(("length", "status"), [(4.99, "fail"), (5.0, "pass"), (5.01, "pass")])
def test_snap_fit_aspect_three_value_boundary(
    enclosure_brief_dict: dict[str, Any], length: float, status: str
) -> None:
    findings = _feature_findings(
        enclosure_brief_dict,
        "PP",
        type="snap_fit",
        face="left",
        length_mm=length,
        width_mm=5,
        hook_thickness_mm=1,
        deflection_mm=0.1,
    )
    assert _rule(findings, "snap_fit_aspect") == status


def test_snap_fit_without_beam_parameters_fails(enclosure_brief_dict: dict[str, Any]) -> None:
    findings = _feature_findings(enclosure_brief_dict, "ABS", type="snap_fit", face="left")
    assert [f.rule_id for f in findings] == ["snap_fit_params"]
    assert findings[0].status == "fail"


# Living hinge: PP max web 0.4 mm; PLA is not hinge-capable.
@pytest.mark.parametrize(
    ("material", "web", "rule", "status"),
    [
        ("PP", 0.39, "living_hinge_web", "pass"),
        ("PP", 0.4, "living_hinge_web", "pass"),
        ("PP", 0.41, "living_hinge_web", "fail"),
        ("PLA", 0.3, "living_hinge_material", "fail"),
        ("PP", None, "living_hinge_params", "fail"),
    ],
)
def test_living_hinge_decision_table(
    enclosure_brief_dict: dict[str, Any],
    material: str,
    web: float | None,
    rule: str,
    status: str,
) -> None:
    feature: dict[str, Any] = {"type": "living_hinge"}
    if web is not None:
        feature["web_thickness_mm"] = web
    findings = _feature_findings(enclosure_brief_dict, material, **feature)
    assert [f.rule_id for f in findings] == [rule]
    assert findings[0].status == status


# Rib: fdm ratio 1.0 x enclosure wall 2.0 mm.
@pytest.mark.parametrize(("thickness", "status"), [(1.99, "pass"), (2.0, "pass"), (2.01, "fail")])
def test_rib_wall_ratio_three_value_boundary(
    enclosure_brief_dict: dict[str, Any], thickness: float, status: str
) -> None:
    findings = _feature_findings(
        enclosure_brief_dict,
        "ABS",
        type="rib",
        length_mm=10,
        height_mm=5,
        thickness_mm=thickness,
    )
    assert _rule(findings, "rib_wall_ratio") == status


@pytest.mark.parametrize(
    ("feature", "rule"),
    [
        ({"length_mm": 10, "thickness_mm": 1}, "rib_params"),
        ({"height_mm": 5, "thickness_mm": 1}, "rib_params"),
        ({"length_mm": 10, "height_mm": 5}, "rib_thickness"),
    ],
)
def test_rib_missing_parameters_fail(
    enclosure_brief_dict: dict[str, Any], feature: dict[str, Any], rule: str
) -> None:
    findings = _feature_findings(enclosure_brief_dict, "ABS", type="rib", **feature)
    assert [(f.rule_id, f.status) for f in findings] == [(rule, "fail")]


@pytest.mark.parametrize(("od", "status"), [(5.99, "fail"), (6.0, "pass"), (6.01, "pass")])
def test_boss_od_ratio_three_value_boundary(
    enclosure_brief_dict: dict[str, Any], od: float, status: str
) -> None:
    findings = _feature_findings(
        enclosure_brief_dict, "ABS", type="boss", od_mm=od, id_mm=3.0, height_mm=5
    )
    assert _rule(findings, "boss_od_ratio") == status


# fdm min wall 0.8 mm: (3.6 - 2.0) / 2 is exactly 0.8 in binary floating point.
@pytest.mark.parametrize(("od", "status"), [(3.58, "fail"), (3.6, "pass"), (3.62, "pass")])
def test_boss_min_wall_three_value_boundary(
    enclosure_brief_dict: dict[str, Any], od: float, status: str
) -> None:
    findings = _feature_findings(
        enclosure_brief_dict, "ABS", type="boss", od_mm=od, id_mm=2.0, height_mm=5
    )
    assert _rule(findings, "boss_min_wall") == status


def test_boss_without_inner_diameter_fails(enclosure_brief_dict: dict[str, Any]) -> None:
    findings = _feature_findings(enclosure_brief_dict, "ABS", type="boss", od_mm=6.0, height_mm=5)
    assert [(f.rule_id, f.status) for f in findings] == [("boss_params", "fail")]


@pytest.mark.parametrize(
    ("angle", "rule", "status"),
    [
        (44.99, "detent_ramp", "pass"),
        (45.0, "detent_ramp", "pass"),
        (45.01, "detent_ramp", "fail"),
        (None, "detent_params", "fail"),
    ],
)
def test_detent_ramp_three_value_boundary(
    enclosure_brief_dict: dict[str, Any], angle: float | None, rule: str, status: str
) -> None:
    feature: dict[str, Any] = {"type": "detent", "depth_mm": 0.5}
    if angle is not None:
        feature["ramp_angle_deg"] = angle
    findings = _feature_findings(enclosure_brief_dict, "ABS", **feature)
    assert [(f.rule_id, f.status) for f in findings] == [(rule, status)]


@pytest.mark.parametrize("mount", ["shell", "lid"])
def test_enclosure_mounts_are_accepted(enclosure_brief_dict: dict[str, Any], mount: str) -> None:
    data = copy.deepcopy(enclosure_brief_dict)
    data["mechanism_features"] = [
        {"id": "F1", "type": "detent", "mount": mount, "ramp_angle_deg": 30, "depth_mm": 0.5}
    ]
    findings = check_mechanism_features(DesignBrief.model_validate(data))
    assert [f.rule_id for f in findings] == ["detent_ramp"]


def test_rib_on_a_bracket_uses_the_sheet_thickness(bracket_brief_dict: dict[str, Any]) -> None:
    data = copy.deepcopy(bracket_brief_dict)
    data["mechanism_features"] = [
        {
            "id": "F1",
            "type": "rib",
            "mount": "base",
            "length_mm": 10,
            "height_mm": 5,
            "thickness_mm": 3.01,
        }
    ]
    findings = check_mechanism_features(DesignBrief.model_validate(data))
    assert [(f.rule_id, f.status, f.limit) for f in findings] == [("rib_wall_ratio", "fail", 3.0)]


def test_spur_gear_min_teeth_table() -> None:
    assert spur_gear_min_teeth(20.0) == 18
    assert spur_gear_min_teeth(14.5) == 32
    assert spur_gear_min_teeth(25.0) == 12
    previous = math.inf
    for tenths in range(10, 301):
        z_min = spur_gear_min_teeth(tenths / 10)
        assert z_min <= previous
        previous = z_min


@pytest.mark.parametrize(("teeth", "status"), [(17, "fail"), (18, "pass"), (19, "pass")])
def test_gear_undercut_three_value_boundary(
    gear_brief_dict: dict[str, Any], teeth: int, status: str
) -> None:
    gear_brief_dict["spur_gear"]["teeth"] = teeth
    findings = check_gear_rules(DesignBrief.model_validate(gear_brief_dict))
    assert _rule(findings, "gear_undercut") == status


# Backlash limit 0.2 * module = 0.2 * 1.5.
@pytest.mark.parametrize(
    ("backlash", "statuses"),
    [(0.0, []), (0.29, ["pass"]), (0.3, ["pass"]), (0.31, ["fail"])],
)
def test_gear_backlash_three_value_boundary(
    gear_brief_dict: dict[str, Any], backlash: float, statuses: list[str]
) -> None:
    gear_brief_dict["spur_gear"]["backlash_mm"] = backlash
    findings = check_gear_rules(DesignBrief.model_validate(gear_brief_dict))
    assert [f.status for f in findings if f.rule_id == "gear_backlash"] == statuses


def test_non_gear_brief_has_no_gear_findings(enclosure_brief: DesignBrief) -> None:
    assert check_gear_rules(enclosure_brief) == []
