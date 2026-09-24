from __future__ import annotations

import hashlib
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


def _evidence_intake(brief: DesignBrief, tmp_path: Path) -> tuple[Intake, Path]:
    payload = b"pretend photo"
    image = tmp_path / "attachments" / "abcd1234abcd.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(payload)
    data = _intake_dict(brief)
    data["assumptions"][0]["evidence"] = {
        "kind": "image",
        "path": str(image.relative_to(tmp_path)),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "note": "connector photo from the user",
    }
    intake = Intake.model_validate(data)
    return intake, tmp_path / "b.intake.json"


def test_evidence_ref_valid_passes(enclosure_brief: DesignBrief, tmp_path: Path):
    intake, intake_path = _evidence_intake(enclosure_brief, tmp_path)
    report = check_intake(enclosure_brief, intake, tmp_path / "b.json", intake_path)
    assert report.verdict == "ready"
    assert report.evidence_errors == []


def test_evidence_missing_file_blocks(enclosure_brief: DesignBrief, tmp_path: Path):
    intake, intake_path = _evidence_intake(enclosure_brief, tmp_path)
    (tmp_path / "attachments" / "abcd1234abcd.png").unlink()
    report = check_intake(enclosure_brief, intake, tmp_path / "b.json", intake_path)
    assert report.verdict == "blocked"
    assert report.evidence_errors == [
        f"{intake.assumptions[0].id} evidence attachments/abcd1234abcd.png: file missing"
    ]


def test_evidence_sha_mismatch_blocks(enclosure_brief: DesignBrief, tmp_path: Path):
    intake, intake_path = _evidence_intake(enclosure_brief, tmp_path)
    (tmp_path / "attachments" / "abcd1234abcd.png").write_bytes(b"tampered")
    report = check_intake(enclosure_brief, intake, tmp_path / "b.json", intake_path)
    assert report.verdict == "blocked"
    assert report.evidence_errors == [
        f"{intake.assumptions[0].id} evidence attachments/abcd1234abcd.png: sha256 mismatch"
    ]
