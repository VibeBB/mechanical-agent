from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from mech.brief import DesignBrief
from mech.cli import main
from mech.sim_request import ruggedness_brief, write_sim_request

MATERIAL = {"youngs_mpa": 18600, "poisson": 0.12, "density_kg_m3": 1850, "component_mass_g": 20}
PART = {
    "ref": "U1",
    "x_mm": 0,
    "y_mm": 0,
    "length_mm": 20,
    "parallel_to": "width",
    "steinberg_c": 1.0,
}
REQUEST_KEYS = {
    "schema_version",
    "from_system",
    "request_id",
    "kind",
    "brief_path",
    "question",
    "requested_by",
}


def _brief(base: dict[str, Any], ruggedness: dict[str, Any] | None) -> DesignBrief:
    enclosure = {**base["enclosure"], "ruggedness": ruggedness}
    return DesignBrief.model_validate({**base, "enclosure": enclosure})


def _full() -> dict[str, Any]:
    return {
        "board_material": MATERIAL,
        "vibration": {"psd_g2_hz": 0.04, "min_fn_hz": 200, "parts": [PART]},
        "drop": {"height_mm": 1000, "pulse_ms": 1, "restitution": 0.5, "max_shock_g": 1500},
        "ip_code": "IP54",
        "sealed": True,
    }


def test_brief_maps_board_openings_and_targets(enclosure_brief_dict: dict[str, Any]) -> None:
    payload = ruggedness_brief(_brief(enclosure_brief_dict, _full()))
    section = payload["ruggedness"]
    assert payload["schema_version"] == 1
    assert payload["name"] == "demo-ruggedness"
    assert section["plate"] == {"width_mm": 60, "depth_mm": 40, "thickness_mm": 1.6, **MATERIAL}
    assert section["vibration"] == {"psd_g2_hz": 0.04, "min_fn_hz": 200, "parts": [PART]}
    assert section["drop"]["restitution"] == 0.5
    assert section["ingress"] == {"code": "IP54", "openings_min_mm": [6, 2.0], "sealed": True}


def test_write_request_is_hash_bound_and_deterministic(
    enclosure_brief_dict: dict[str, Any], tmp_path: Path
) -> None:
    brief = _brief(enclosure_brief_dict, _full())
    first = write_sim_request(brief, tmp_path / "sim", root=tmp_path)
    request_path = Path(first["request"])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert set(request) == REQUEST_KEYS
    assert request["kind"] == "ruggedness"
    assert request["from_system"] == "mech"
    assert request["brief_path"] == "sim/demo.ruggedness.sim.json"
    assert request["request_id"] == f"demo-ruggedness-{first['sim_brief_sha256'][:12]}"
    assert first["checks"] == ["drop", "ingress", "vibration"]
    before = request_path.read_bytes()
    assert write_sim_request(brief, tmp_path / "sim", root=tmp_path) == first
    assert request_path.read_bytes() == before


def test_drop_only_request_needs_no_board(enclosure_brief_dict: dict[str, Any]) -> None:
    base = {**enclosure_brief_dict, "enclosure": {**enclosure_brief_dict["enclosure"]}}
    base["enclosure"]["board"] = None
    drop = {"drop": _full()["drop"]}
    assert set(ruggedness_brief(_brief(base, drop))["ruggedness"]) == {"drop"}
    with pytest.raises(ValueError, match=r"enclosure\.board"):
        ruggedness_brief(_brief(base, {**_full(), "drop": None, "ip_code": None}))


@pytest.mark.parametrize(
    "ruggedness",
    [
        {},
        {"vibration": {"psd_g2_hz": 0.04, "parts": [PART]}},
        {"board_material": MATERIAL, "vibration": {"psd_g2_hz": 0.04, "parts": [PART, PART]}},
        {"ip_code": "IP7X"},
        {"drop": {"height_mm": 1, "pulse_ms": 1, "restitution": 1.1, "max_shock_g": 1}},
    ],
)
def test_malformed_ruggedness_is_rejected(
    enclosure_brief_dict: dict[str, Any], ruggedness: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        _brief(enclosure_brief_dict, ruggedness)


def test_cli_sim_request(
    enclosure_brief_dict: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "demo.brief.json"
    brief = {**enclosure_brief_dict}
    brief["enclosure"] = {**brief["enclosure"], "ruggedness": {"ip_code": "IP40"}}
    path.write_text(json.dumps(brief), encoding="utf-8")
    args = ["sim-request", "--brief", str(path), "--out-dir", str(tmp_path / "sim")]
    assert main([*args, "--workspace", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["sim_brief"] == "sim/demo.ruggedness.sim.json"
    path.write_text(json.dumps(enclosure_brief_dict), encoding="utf-8")
    assert main(args) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "fail"


def test_mcp_sim_request_is_workspace_relative(
    enclosure_brief_dict: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from mech.mcp_server import call_tool

    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    brief = {**enclosure_brief_dict}
    brief["enclosure"] = {**brief["enclosure"], "ruggedness": {"ip_code": "IP40"}}
    result = call_tool("mech_sim_request", {"brief": brief, "out_dir": "sim"})
    assert not result.isError
    request = json.loads((tmp_path / "sim" / "demo.ruggedness.sim-request.json").read_text("utf-8"))
    assert request["brief_path"] == "sim/demo.ruggedness.sim.json"
    outside = call_tool("mech_sim_request", {"brief": brief, "out_dir": str(tmp_path.parent)})
    assert outside.isError
