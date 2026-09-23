from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mech.brief import DesignBrief
from mech.generators import generate


def test_enclosure_generates(enclosure_brief: DesignBrief):
    design = generate(enclosure_brief)
    part_ids = {part.part_id for part in design.parts}
    assert part_ids == {"shell", "lid"}
    assert all(part.shape.is_valid for part in design.parts)


def test_enclosure_opening_meshes(enclosure_brief: DesignBrief, tmp_path: Path):
    import build123d as b

    design = generate(enclosure_brief)
    mesher: Any = b.Mesher()
    for part in design.parts:
        mesher.add_shape(b.Compound(children=[part.shape]), linear_deflection=0.1)
    out = tmp_path / "m.3mf"
    mesher.write(str(out))
    assert out.stat().st_size > 0


def test_bracket_generates(bracket_brief_dict: dict[str, Any]):
    brief = DesignBrief.model_validate(bracket_brief_dict)
    design = generate(brief)
    assert len(design.parts) == 1
    assert design.parts[0].shape.is_valid


def test_gear_generates(gear_brief_dict: dict[str, Any]):
    brief = DesignBrief.model_validate(gear_brief_dict)
    design = generate(brief)
    assert len(design.parts) == 1
    assert design.parts[0].shape.is_valid
    assert design.parts[0].shape.volume > 0


def test_snap_lid_variant(enclosure_brief_dict: dict[str, Any]):
    enclosure_brief_dict["enclosure"]["lid"] = "snap"
    enclosure_brief_dict["mechanism_features"] = [
        {
            "id": "F1",
            "type": "snap_fit",
            "mount": "lid",
            "face": "right",
            "x_mm": 0,
            "z_mm": 2,
            "length_mm": 8,
            "width_mm": 4,
            "hook_thickness_mm": 1.0,
            "deflection_mm": 0.5,
        }
    ]
    brief = DesignBrief.model_validate(enclosure_brief_dict)
    design = generate(brief)
    assert {p.part_id for p in design.parts} == {"shell", "lid"}
    assert all(p.shape.is_valid for p in design.parts)


def test_unknown_design_type_rejected(enclosure_brief_dict: dict[str, Any]):
    from pydantic import ValidationError

    enclosure_brief_dict["design_type"] = "fixture"
    with pytest.raises(ValidationError):
        DesignBrief.model_validate(enclosure_brief_dict)
