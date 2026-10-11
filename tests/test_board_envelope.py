from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mech.board_envelope import board_envelope_payload, write_board_envelope
from mech.brief import DesignBrief, brief_sha256
from mech.cli import main

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "enclosure.brief.json"


def _brief(**enclosure: object) -> DesignBrief:
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["enclosure"].update(enclosure)
    return DesignBrief.model_validate(data)


def test_payload_projects_the_cavity_into_the_board_frame() -> None:
    brief = _brief()
    payload = board_envelope_payload(brief)
    assert payload["artifact_kind"] == "mech_board_envelope"
    assert payload["frame"] == "board_center_y_up_mm"
    assert payload["brief_sha256"] == brief_sha256(brief)
    assert payload["board"]["width_mm"] == 60
    assert len(payload["board"]["mount_holes"]) == 4
    # height 30 - wall 2 - (floor 2 + standoff 5 + board 1.6)
    assert payload["max_height_top_mm"] == pytest.approx(19.4)
    assert payload["max_height_bottom_mm"] == pytest.approx(5.0)
    assert payload["openings"] == [
        {"id": "O1", "face": "front", "along_mm": [-6.0, 6.0], "z_mm": [3.4, 9.4]}
    ]


def test_round_and_lid_openings() -> None:
    brief = _brief(
        openings=[
            {
                "id": "O1",
                "face": "left",
                "kind": "round",
                "width_mm": 4,
                "height_mm": 4,
                "center_x_mm": 10,
                "center_y_mm": -2,
            },
            {"id": "O2", "face": "top", "width_mm": 5, "height_mm": 5},
        ]
    )
    openings = board_envelope_payload(brief)["openings"]
    assert openings == [{"id": "O1", "face": "left", "along_mm": [8.0, 12.0], "z_mm": [2.4, 6.4]}]


def test_brief_without_board_is_refused() -> None:
    brief = _brief(board=None)
    with pytest.raises(ValueError, match="no enclosure board"):
        board_envelope_payload(brief)


def test_write_pins_the_bytes(tmp_path: Path) -> None:
    result = write_board_envelope(_brief(), tmp_path)
    path = Path(result["path"])
    assert path.name == "demo.mech-board-envelope.json"
    assert result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert write_board_envelope(_brief(), tmp_path)["sha256"] == result["sha256"]


def test_cli_reports_a_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["enclosure"]["board"] = None
    brief = tmp_path / "b.json"
    brief.write_text(json.dumps(data), encoding="utf-8")
    main(["board-envelope", "--brief", str(brief), "--out-dir", str(tmp_path)])
    assert '"stage": "board-envelope"' in capsys.readouterr().out
