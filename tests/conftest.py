from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mech.brief import DesignBrief


@pytest.fixture()
def enclosure_brief_dict() -> dict[str, Any]:
    return {
        "name": "demo",
        "design_type": "enclosure",
        "material": "ABS",
        "process": "fdm",
        "enclosure": {
            "width_mm": 80,
            "depth_mm": 60,
            "height_mm": 30,
            "wall_mm": 2.0,
            "floor_mm": 2.0,
            "lid": "screw",
            "corner_radius_mm": 3.0,
            "clearance_mm": 0.3,
            "standoff_height_mm": 5.0,
            "board": {
                "width_mm": 60,
                "depth_mm": 40,
                "thickness_mm": 1.6,
                "keepout_height_mm": 8.0,
                "mount_holes": [
                    {"id": "MH1", "x_mm": -25, "y_mm": -15, "diameter_mm": 3.2},
                    {"id": "MH2", "x_mm": 25, "y_mm": -15, "diameter_mm": 3.2},
                    {"id": "MH3", "x_mm": -25, "y_mm": 15, "diameter_mm": 3.2},
                    {"id": "MH4", "x_mm": 25, "y_mm": 15, "diameter_mm": 3.2},
                ],
            },
            "openings": [
                {
                    "id": "O1",
                    "face": "front",
                    "kind": "rect",
                    "width_mm": 12,
                    "height_mm": 6,
                }
            ],
            "vent": {
                "face": "left",
                "slot_width_mm": 2.0,
                "slot_length_mm": 25.0,
                "slot_pitch_mm": 5.0,
                "margin_mm": 8.0,
            },
            "screw": {"size": "M3", "boss_diameter_mm": 7.0},
        },
        "fits": [
            {
                "id": "FT1",
                "feature": "shell",
                "nominal_mm": 5.0,
                "hole_class": "H7",
                "shaft_class": "g6",
                "intent": "clearance",
            }
        ],
        "stackups": [
            {
                "id": "SC1",
                "min_mm": 2.0,
                "max_mm": 2.5,
                "elements": [
                    {
                        "name": "wall",
                        "nominal_mm": 2.0,
                        "plus_mm": 0.1,
                        "minus_mm": 0.1,
                    },
                    {
                        "name": "gap",
                        "nominal_mm": 0.3,
                        "plus_mm": 0.05,
                        "minus_mm": 0.15,
                    },
                ],
            }
        ],
    }


@pytest.fixture()
def enclosure_brief(enclosure_brief_dict: dict[str, Any]) -> DesignBrief:
    return DesignBrief.model_validate(enclosure_brief_dict)


@pytest.fixture()
def bracket_brief_dict() -> dict[str, Any]:
    return {
        "name": "bracket-demo",
        "design_type": "bracket",
        "material": "SUS304",
        "process": "machining",
        "bracket": {
            "form": "l",
            "width_mm": 40,
            "thickness_mm": 3,
            "base_mm": 60,
            "leg_mm": 40,
            "inner_fillet_mm": 2.0,
            "gusset": True,
            "holes": [
                {
                    "id": "H1",
                    "face": "base",
                    "x_mm": 10,
                    "y_mm": 0,
                    "diameter_mm": 5,
                },
                {
                    "id": "H2",
                    "face": "leg",
                    "x_mm": 0,
                    "y_mm": 10,
                    "diameter_mm": 5,
                },
            ],
        },
    }


@pytest.fixture()
def gear_brief_dict() -> dict[str, Any]:
    return {
        "name": "gear-demo",
        "design_type": "spur_gear",
        "material": "SUS304",
        "process": "machining",
        "spur_gear": {
            "module_mm": 1.5,
            "teeth": 20,
            "thickness_mm": 8,
            "bore_mm": 6,
            "pressure_angle_deg": 20.0,
            "backlash_mm": 0.1,
            "hub_diameter_mm": 15,
            "hub_height_mm": 5,
        },
    }


@pytest.fixture()
def brief_path(tmp_path: Path, enclosure_brief_dict: dict[str, Any]) -> Path:
    path = tmp_path / "demo.brief.json"
    path.write_text(json.dumps(enclosure_brief_dict), encoding="utf-8")
    return path
