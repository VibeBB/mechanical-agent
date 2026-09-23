from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from mech.brief import DesignBrief, brief_sha256, load_brief


def test_valid_enclosure(enclosure_brief_dict: dict[str, Any]):
    brief = DesignBrief.model_validate(enclosure_brief_dict)
    assert brief.design_type == "enclosure"
    assert brief.part_ids() == ["shell", "lid"]
    assert "MH1" in brief.feature_ids()
    assert "O1" in brief.feature_ids()


def test_spec_exclusivity(enclosure_brief_dict: dict[str, Any], bracket_brief_dict: dict[str, Any]):
    enclosure_brief_dict["bracket"] = bracket_brief_dict["bracket"]
    with pytest.raises(ValidationError, match="must be null"):
        DesignBrief.model_validate(enclosure_brief_dict)


def test_design_type_requires_spec(enclosure_brief_dict: dict[str, Any]):
    enclosure_brief_dict["enclosure"] = None
    with pytest.raises(ValidationError, match="requires its spec block"):
        DesignBrief.model_validate(enclosure_brief_dict)


def test_unknown_material_rejected(enclosure_brief_dict: dict[str, Any]):
    enclosure_brief_dict["material"] = "TITANIUM"
    with pytest.raises(ValidationError, match="unsupported material"):
        DesignBrief.model_validate(enclosure_brief_dict)


def test_unknown_process_rejected(enclosure_brief_dict: dict[str, Any]):
    enclosure_brief_dict["process"] = "sla"
    with pytest.raises(ValidationError, match="Input should be"):
        DesignBrief.model_validate(enclosure_brief_dict)


def test_extra_field_rejected(enclosure_brief_dict: dict[str, Any]):
    enclosure_brief_dict["enclosure"]["bogus_mm"] = 5
    with pytest.raises(ValidationError):
        DesignBrief.model_validate(enclosure_brief_dict)


def test_fit_references_known_feature(enclosure_brief_dict: dict[str, Any]):
    enclosure_brief_dict["fits"] = [
        {
            "id": "FT1",
            "feature": "nosuch",
            "nominal_mm": 5,
            "hole_class": "H7",
            "shaft_class": "g6",
            "intent": "clearance",
        }
    ]
    with pytest.raises(ValidationError, match="unknown feature"):
        DesignBrief.model_validate(enclosure_brief_dict)


def test_sha256_deterministic(enclosure_brief: DesignBrief):
    assert brief_sha256(enclosure_brief) == brief_sha256(enclosure_brief)


def test_sha256_changes_on_mutation(
    enclosure_brief: DesignBrief, enclosure_brief_dict: dict[str, Any]
):
    enclosure_brief_dict["enclosure"]["width_mm"] = 81
    mutated = DesignBrief.model_validate(enclosure_brief_dict)
    assert brief_sha256(enclosure_brief) != brief_sha256(mutated)


def test_load_brief_bad_json(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="could not load"):
        load_brief(path)


def test_load_brief_schema_error(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text('{"design_type": 3}', encoding="utf-8")
    with pytest.raises(ValidationError):
        load_brief(path)
