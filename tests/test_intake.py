from __future__ import annotations

from pathlib import Path
from typing import Any

from mech.brief import DesignBrief, brief_sha256
from mech.intake import Intake, IntakeReport, check_intake


def _intake_dict(brief: DesignBrief) -> dict[str, Any]:
    return {
        "brief_sha256": brief_sha256(brief),
        "requirements": [
            {"id": "R1", "text": "80x60x30 ABS box", "source": "user", "speaker": "user"},
            {"id": "R2", "text": "front opening", "source": "user", "speaker": "user"},
        ],
        "assumptions": [
            {"id": "A1", "text": "screw lid", "rationale": "user did not specify"},
        ],
        "open_questions": [],
        "part_sources": {p: ["R1"] for p in brief.part_ids()},
        "feature_sources": {f: ["R1"] for f in brief.feature_ids()},
    }


def _check(brief: DesignBrief, data: dict[str, Any], tmp_path: Path) -> IntakeReport:
    intake = Intake.model_validate(data)
    return check_intake(brief, intake, tmp_path / "b.json", tmp_path / "i.json")


def test_ready_when_fully_mapped(enclosure_brief: DesignBrief, tmp_path: Path):
    report = _check(enclosure_brief, _intake_dict(enclosure_brief), tmp_path)
    assert report.verdict == "ready"
    assert report.sha_matches


def test_open_question_blocks(enclosure_brief: DesignBrief, tmp_path: Path):
    data = _intake_dict(enclosure_brief)
    data["open_questions"] = [{"id": "Q1", "text": "lid type?"}]
    report = _check(enclosure_brief, data, tmp_path)
    assert report.verdict == "blocked"


def test_unmapped_part_blocks(enclosure_brief: DesignBrief, tmp_path: Path):
    data = _intake_dict(enclosure_brief)
    data["part_sources"] = {"shell": ["R1"]}
    report = _check(enclosure_brief, data, tmp_path)
    assert report.verdict == "blocked"
    assert "lid" in report.unmapped_parts


def test_unknown_source_id_blocks(enclosure_brief: DesignBrief, tmp_path: Path):
    data = _intake_dict(enclosure_brief)
    data["feature_sources"]["O1"] = ["R99"]
    report = _check(enclosure_brief, data, tmp_path)
    assert report.verdict == "blocked"


def test_corrupted_brief_fails_sha(
    enclosure_brief: DesignBrief,
    enclosure_brief_dict: dict[str, Any],
    tmp_path: Path,
):
    """Negative test: a mutated brief must fail the provenance hash check."""
    data = _intake_dict(enclosure_brief)
    # brief mutated after the intake document was written
    enclosure_brief_dict["enclosure"]["width_mm"] = 81
    mutated = DesignBrief.model_validate(enclosure_brief_dict)
    report = _check(mutated, data, tmp_path)
    assert report.verdict == "blocked"
    assert not report.sha_matches
