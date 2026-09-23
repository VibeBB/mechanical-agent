from __future__ import annotations

from typing import Any

from mech.brief import DesignBrief
from mech.dfm import check_dfm, check_standoff_bosses
from mech.mechanism import check_gear_rules, check_mechanism_features


def test_wall_under_minimum_fails(
    enclosure_brief: DesignBrief, enclosure_brief_dict: dict[str, Any]
):
    enclosure_brief_dict["enclosure"]["wall_mm"] = 0.4
    brief = DesignBrief.model_validate(enclosure_brief_dict)
    findings = check_dfm(brief, measured_min_wall_mm=0.4)
    wall = [f for f in findings if "wall" in f.rule_id]
    assert wall and all(f.status == "fail" for f in wall)


def test_nominal_wall_passes(enclosure_brief: DesignBrief):
    findings = check_dfm(enclosure_brief, measured_min_wall_mm=2.0)
    wall = [f for f in findings if "wall" in f.rule_id and f.status == "fail"]
    assert not wall


def test_measured_wall_below_declared_fails(enclosure_brief: DesignBrief):
    findings = check_dfm(enclosure_brief, measured_min_wall_mm=0.5)
    measured = [f for f in findings if f.rule_id == "measured_wall"]
    assert measured and measured[0].status == "fail"


def test_standoff_geometry_rule(enclosure_brief: DesignBrief):
    findings = check_standoff_bosses(enclosure_brief)
    assert findings and all(f.status == "pass" for f in findings)


def test_gear_teeth_undercut(enclosure_brief_dict: dict[str, Any], gear_brief_dict: dict[str, Any]):
    gear_brief_dict["spur_gear"]["teeth"] = 14
    brief = DesignBrief.model_validate(gear_brief_dict)
    findings = check_gear_rules(brief)
    undercut = [f for f in findings if "undercut" in f.rule_id or "teeth" in f.rule_id]
    assert undercut and undercut[0].status == "fail"


def test_gear_backlash_limit(gear_brief_dict: dict[str, Any]):
    gear_brief_dict["spur_gear"]["backlash_mm"] = 1.0
    brief = DesignBrief.model_validate(gear_brief_dict)
    findings = check_gear_rules(brief)
    backlash = [f for f in findings if "backlash" in f.rule_id]
    assert backlash and backlash[0].status == "fail"


def test_gear_nominal_passes(gear_brief_dict: dict[str, Any]):
    brief = DesignBrief.model_validate(gear_brief_dict)
    findings = check_gear_rules(brief)
    assert all(f.status == "pass" for f in findings)


def test_snap_fit_strain_limit(enclosure_brief_dict: dict[str, Any]):
    enclosure_brief_dict["material"] = "PLA"
    enclosure_brief_dict["mechanism_features"] = [
        {
            "id": "F1",
            "type": "snap_fit",
            "mount": "shell",
            "face": "left",
            "x_mm": 0,
            "y_mm": 0,
            "z_mm": 8,
            "length_mm": 4,
            "width_mm": 5,
            "hook_thickness_mm": 1.5,
            "deflection_mm": 1.5,
        }
    ]
    brief = DesignBrief.model_validate(enclosure_brief_dict)
    findings = check_mechanism_features(brief)
    strain = [f for f in findings if "strain" in f.rule_id]
    assert strain and strain[0].status == "fail"


def test_unknown_feature_type_absent(enclosure_brief: DesignBrief):
    findings = check_mechanism_features(enclosure_brief)
    assert isinstance(findings, list)
