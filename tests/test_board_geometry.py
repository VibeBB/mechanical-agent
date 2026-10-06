from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from mech.board_geometry import suggest_board
from mech.brief import BoardSpec, DesignBrief
from mech.cli import main
from mech.gates import _board_geometry_checks  # pyright: ignore[reportPrivateUsage]


def _geometry() -> dict[str, Any]:
    holes = [(-25, -15), (25, -15), (-25, 15), (25, 15)]
    return {
        "artifact_kind": "circuit_board_geometry",
        "schema_version": 1,
        "frame": "board_center_y_up_mm",
        "pcb": {"path": "demo.kicad_pcb", "sha256": "a" * 64},
        "part_specs": {},
        "step": None,
        "width_mm": 60.0,
        "depth_mm": 40.0,
        "thickness_mm": 1.6,
        "outline_mm": [[-30, -20], [30, -20], [30, 20], [-30, 20]],
        "mount_holes": [
            {"ref": f"H{i}", "x_mm": x, "y_mm": y, "diameter_mm": 3.2}
            for i, (x, y) in enumerate(holes, start=1)
        ],
        "components": [
            {
                "ref": "J1",
                "lib_id": "Connector_USB:USB_C",
                "side": "top",
                "x_mm": 0.0,
                "y_mm": -17.0,
                "rotation_deg": 0.0,
                "bbox_mm": [-4.25, -20.0, 4.25, -14.0],
                "height_mm": 3.5,
                "height_sources": ["step_model"],
                "connector": True,
                "edge": "front",
            }
        ],
        "max_height_top_mm": 8.0,
        "max_height_bottom_mm": None,
        "unknown": [],
        "verdict": "pass",
    }


def _setup(
    tmp_path: Path, brief_dict: dict[str, Any], geometry: dict[str, Any]
) -> tuple[DesignBrief, Path]:
    path = tmp_path / "demo.board-geometry.json"
    path.write_text(json.dumps(geometry), encoding="utf-8")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    data = copy.deepcopy(brief_dict)
    data["enclosure"]["board"]["source"] = {"path": path.name, "sha256": sha}
    data["enclosure"]["openings"][0]["center_y_mm"] = -3.0
    return DesignBrief.model_validate(data), path


def _status(checks: list[Any]) -> dict[str, str]:
    return {c.subject: c.status for c in checks}


def test_matching_board_passes(tmp_path: Path, enclosure_brief_dict: dict[str, Any]) -> None:
    brief, path = _setup(tmp_path, enclosure_brief_dict, _geometry())
    status = _status(_board_geometry_checks(brief, path))
    assert set(status.values()) == {"pass"}
    assert {"source", "width", "depth", "thickness", "keepout_height", "mount_holes"} < set(status)
    assert status["connector:J1"] == "pass"


def test_unpinned_board_has_no_checks(enclosure_brief: DesignBrief) -> None:
    assert _board_geometry_checks(enclosure_brief, None) == []


def test_missing_and_stale_pins_fail_closed(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    brief, path = _setup(tmp_path, enclosure_brief_dict, _geometry())
    assert _status(_board_geometry_checks(brief, tmp_path / "absent.json")) == {"source": "unknown"}
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    checks = _board_geometry_checks(brief, path)
    assert [c.status for c in checks] == ["fail"]
    assert "stale pin" in checks[0].detail


def test_incomplete_or_malformed_geometry_is_unknown(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    geometry = _geometry() | {"verdict": "fail", "unknown": ["J1: height"]}
    brief, path = _setup(tmp_path, enclosure_brief_dict, geometry)
    assert _status(_board_geometry_checks(brief, path)) == {"source": "unknown"}
    brief, path = _setup(tmp_path, enclosure_brief_dict, _geometry() | {"extra": 1})
    assert _status(_board_geometry_checks(brief, path)) == {"source": "unknown"}


@pytest.mark.parametrize(("delta", "expected"), [(0.04, "pass"), (0.05, "pass"), (0.06, "fail")])
def test_width_tolerance_boundary(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any], delta: float, expected: str
) -> None:
    brief, path = _setup(tmp_path, enclosure_brief_dict, _geometry() | {"width_mm": 60 + delta})
    assert _status(_board_geometry_checks(brief, path))["width"] == expected


@pytest.mark.parametrize(("top", "expected"), [(7.99, "pass"), (8.0, "pass"), (8.01, "fail")])
def test_keepout_boundary(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any], top: float, expected: str
) -> None:
    geometry = _geometry() | {"max_height_top_mm": top}
    brief, path = _setup(tmp_path, enclosure_brief_dict, geometry)
    assert _status(_board_geometry_checks(brief, path))["keepout_height"] == expected


@pytest.mark.parametrize(("shift", "expected"), [(0.05, "pass"), (0.06, "fail")])
def test_mount_hole_position_boundary(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any], shift: float, expected: str
) -> None:
    geometry = _geometry()
    geometry["mount_holes"][0]["x_mm"] += shift
    brief, path = _setup(tmp_path, enclosure_brief_dict, geometry)
    assert _status(_board_geometry_checks(brief, path))["mount_holes"] == expected


def test_extra_brief_hole_fails(tmp_path: Path, enclosure_brief_dict: dict[str, Any]) -> None:
    geometry = _geometry()
    geometry["mount_holes"].pop()
    brief, path = _setup(tmp_path, enclosure_brief_dict, geometry)
    assert _status(_board_geometry_checks(brief, path))["mount_holes"] == "fail"


@pytest.mark.parametrize(
    ("face", "center_y", "expected"),
    [
        ("front", -3.0, "pass"),
        ("back", -3.0, "fail"),
        # opening spans z 12.1..18.1: touching the connector top (12.1) is not access
        ("front", 0.1, "fail"),
    ],
)
def test_connector_needs_an_overlapping_opening(
    tmp_path: Path,
    enclosure_brief_dict: dict[str, Any],
    face: str,
    center_y: float,
    expected: str,
) -> None:
    brief, path = _setup(tmp_path, enclosure_brief_dict, _geometry())
    data = brief.model_dump()
    data["enclosure"]["openings"][0] |= {"face": face, "center_y_mm": center_y}
    brief = DesignBrief.model_validate(data)
    assert _status(_board_geometry_checks(brief, path))["connector:J1"] == expected


def test_suggested_board_round_trips_through_the_gate(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    brief, path = _setup(tmp_path, enclosure_brief_dict, _geometry())
    from mech.board_geometry import load_geometry, sha256_file

    suggestion = suggest_board(load_geometry(path), path.name, sha256_file(path))
    board = BoardSpec.model_validate(suggestion["board"])
    assert [h.id for h in board.mount_holes] == ["MH1", "MH2", "MH3", "MH4"]
    assert suggestion["connector_openings"] == [
        {"ref": "J1", "face": "front", "side": "top", "along_mm": [-4.0, 4.0], "height_mm": 3.5}
    ]
    data = brief.model_dump()
    data["enclosure"]["board"] = board.model_dump()
    rebuilt = DesignBrief.model_validate(data)
    assert set(_status(_board_geometry_checks(rebuilt, path)).values()) == {"pass"}


def test_suggest_rejects_incomplete_geometry(tmp_path: Path) -> None:
    from mech.board_geometry import BoardGeometry

    geometry = BoardGeometry.model_validate(_geometry() | {"verdict": "fail"})
    with pytest.raises(ValueError, match="not complete"):
        suggest_board(geometry, "x.json", "b" * 64)


def test_cli_board_import(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "demo.board-geometry.json"
    path.write_text(json.dumps(_geometry()), encoding="utf-8")
    assert main(["board-import", "--geometry", str(path), "--source-path", "pcb/x.json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["board"]["source"]["path"] == "pcb/x.json"
    path.write_text("{}", encoding="utf-8")
    assert main(["board-import", "--geometry", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "fail"
