from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from mech.appearance import appearance_payload, write_appearance
from mech.brief import DesignBrief, brief_sha256
from mech.cli import main

VIEWING = {
    "distance_mm": 450,
    "illuminance_lux": 1000,
    "time_s": 10,
    "angle_deg": 45,
    "source": "customer cosmetic spec CS-12 rev B",
}


def _appearance() -> dict[str, Any]:
    return {
        "viewing": VIEWING,
        "surfaces": [
            {
                "face": "top",
                "cosmetic_class": "A",
                "defects": [
                    {"defect": "scratch", "max_size_mm": 0.3, "max_count": 1},
                    {"defect": "color_deviation", "max_count": 0, "max_delta": 1.5},
                ],
            },
            {
                "face": "front",
                "cosmetic_class": "B",
                "defects": [{"defect": "layer_line", "max_size_mm": 0.1, "max_count": 3}],
            },
            {"face": "bottom", "cosmetic_class": "C"},
        ],
        "samples": [
            {
                "id": "LS1",
                "face": "top",
                "defect": "scratch",
                "side": "accept",
                "description": "0.3 mm",
            },
            {
                "id": "LS2",
                "face": "top",
                "defect": "scratch",
                "side": "reject",
                "description": "0.4 mm",
            },
            {
                "id": "LS3",
                "face": "top",
                "defect": "color_deviation",
                "side": "accept",
                "description": "dE 1.5",
            },
            {
                "id": "LS4",
                "face": "top",
                "defect": "color_deviation",
                "side": "reject",
                "description": "dE 2.0",
            },
            {
                "id": "LS10",
                "face": "front",
                "defect": "layer_line",
                "side": "accept",
                "description": "0.1 mm",
            },
            {
                "id": "LS9",
                "face": "front",
                "defect": "layer_line",
                "side": "reject",
                "description": "0.15 mm",
            },
        ],
    }


def _brief(base: dict[str, Any], appearance: dict[str, Any] | None, **top: Any) -> DesignBrief:
    return DesignBrief.model_validate({**base, **top, "appearance": appearance})


def test_payload_projects_the_brief(enclosure_brief_dict: dict[str, Any]) -> None:
    brief = _brief(enclosure_brief_dict, _appearance())
    payload = appearance_payload(brief)
    assert payload["artifact_kind"] == "mech_appearance"
    assert payload["system"] == "mech"
    assert payload["brief_sha256"] == brief_sha256(brief)
    assert [surface["face"] for surface in payload["surfaces"]] == ["bottom", "front", "top"]
    assert [d["defect"] for d in payload["surfaces"][2]["defects"]] == [
        "color_deviation",
        "scratch",
    ]
    assert [sample["id"] for sample in payload["samples"]] == [
        "LS1",
        "LS2",
        "LS3",
        "LS4",
        "LS9",
        "LS10",
    ]
    assert payload["surfaces"][2]["defects"][1] == {
        "defect": "scratch",
        "max_size_mm": 0.3,
        "max_count": 1,
        "max_delta": None,
    }


def test_write_is_deterministic(enclosure_brief_dict: dict[str, Any], tmp_path: Path) -> None:
    brief = _brief(enclosure_brief_dict, _appearance())
    first = write_appearance(brief, tmp_path / "a")
    second = write_appearance(brief, tmp_path / "b")
    assert first["sha256"] == second["sha256"]
    path = Path(first["path"])
    assert path.name == "demo.mech-appearance.json"
    assert path.read_bytes().endswith(b"}\n")
    assert first["samples"] == ["LS1", "LS2", "LS3", "LS4", "LS9", "LS10"]


def test_no_appearance_is_refused(enclosure_brief_dict: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="no appearance block"):
        appearance_payload(_brief(enclosure_brief_dict, None))


def _mutated(kind: str) -> dict[str, Any]:
    data = _appearance()
    if kind == "foreign_face":
        data["surfaces"][2]["face"] = "plate"
    elif kind == "duplicate_face":
        data["surfaces"][2]["face"] = "top"
    elif kind == "class_a_without_limits":
        data["surfaces"][0]["defects"] = []
        data["samples"] = data["samples"][4:]
    elif kind == "duplicate_defect":
        data["surfaces"][1]["defects"].append(dict(data["surfaces"][1]["defects"][0]))
    elif kind == "missing_reject":
        data["samples"] = [s for s in data["samples"] if s["id"] != "LS2"]
    elif kind == "two_accepts":
        data["samples"][1]["side"] = "accept"
    elif kind == "undeclared_sample":
        data["samples"].append(
            {"id": "LS20", "face": "bottom", "defect": "dent", "side": "accept", "description": "x"}
        )
    elif kind == "duplicate_sample_id":
        data["samples"][1]["id"] = "LS1"
    elif kind == "delta_with_size":
        data["surfaces"][0]["defects"][1]["max_size_mm"] = 1.0
    elif kind == "size_without_bound":
        del data["surfaces"][0]["defects"][0]["max_size_mm"]
    elif kind == "molding_defect_in_fdm":
        data["surfaces"][0]["defects"][0]["defect"] = "sink_mark"
        for sample in data["samples"][:2]:
            sample["defect"] = "sink_mark"
    elif kind == "bad_sample_id":
        data["samples"][0]["id"] = "S1"
    elif kind == "angle_out_of_range":
        data["viewing"] = {**VIEWING, "angle_deg": 95}
    elif kind == "no_source":
        data["viewing"] = {**VIEWING, "source": ""}
    elif kind == "extra_key":
        data["surfaces"][0]["gloss"] = "matte"
    return data


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("foreign_face", "not a enclosure face"),
        ("duplicate_face", "faces must be unique"),
        ("class_a_without_limits", "needs defect limits"),
        ("duplicate_defect", "lists a defect twice"),
        ("missing_reject", "exactly one accept and one reject"),
        ("two_accepts", "exactly one accept and one reject"),
        ("undeclared_sample", "has no dent limit on face bottom"),
        ("duplicate_sample_id", "ids must be unique"),
        ("delta_with_size", "max_delta only"),
        ("size_without_bound", "max_size_mm only"),
        ("molding_defect_in_fdm", "cannot occur in fdm"),
        ("bad_sample_id", "String should match pattern"),
        ("angle_out_of_range", "less than or equal to 90"),
        ("no_source", "at least 1 character"),
        ("extra_key", "Extra inputs are not permitted"),
    ],
)
def test_bad_appearance_is_rejected(
    enclosure_brief_dict: dict[str, Any], kind: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _brief(enclosure_brief_dict, _mutated(kind))


def test_class_c_limits_may_go_without_samples(enclosure_brief_dict: dict[str, Any]) -> None:
    data = _appearance()
    data["surfaces"][2]["defects"] = [{"defect": "dent", "max_size_mm": 2, "max_count": 2}]
    brief = _brief(enclosure_brief_dict, data)
    assert brief.appearance is not None


def test_molding_defects_are_allowed_for_molding(enclosure_brief_dict: dict[str, Any]) -> None:
    data = _appearance()
    data["surfaces"][1]["defects"] = [{"defect": "sink_mark", "max_size_mm": 0.05, "max_count": 0}]
    for sample in data["samples"][4:]:
        sample["defect"] = "sink_mark"
    brief = _brief(enclosure_brief_dict, data, process="molding")
    assert appearance_payload(brief)["process"] == "molding"
    with pytest.raises(ValidationError, match="cannot occur in molding"):
        _brief(enclosure_brief_dict, _appearance(), process="molding")


def test_cli_appearance(
    enclosure_brief_dict: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    brief_path = tmp_path / "demo.brief.json"
    brief_path.write_text(
        json.dumps({**enclosure_brief_dict, "appearance": _appearance()}), encoding="utf-8"
    )
    rc = main(["appearance", "--brief", str(brief_path), "--out-dir", str(tmp_path / "out")])
    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["verdict"] == "pass"
    assert (tmp_path / "out" / "demo.mech-appearance.json").is_file()

    brief_path.write_text(json.dumps(enclosure_brief_dict), encoding="utf-8")
    rc = main(["appearance", "--brief", str(brief_path), "--out-dir", str(tmp_path / "out")])
    result = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert result["verdict"] == "fail"
    assert "no appearance block" in result["detail"]


def test_mcp_appearance(
    enclosure_brief_dict: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from mech.mcp_server import call_tool

    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    result = call_tool(
        "mech_appearance",
        {"brief": {**enclosure_brief_dict, "appearance": _appearance()}, "out_dir": "out"},
    )
    assert not result.isError
    assert (tmp_path / "out" / "demo.mech-appearance.json").is_file()
    outside = call_tool(
        "mech_appearance",
        {"brief": {**enclosure_brief_dict, "appearance": _appearance()}, "out_dir": "/etc/x"},
    )
    assert outside.isError
