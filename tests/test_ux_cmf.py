from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from mech.brief import DesignBrief
from mech.gates import _cmf_checks  # pyright: ignore[reportPrivateUsage]
from mech.ux_cmf import resolve_cmf


def _appearance() -> dict[str, Any]:
    return {
        "viewing": {
            "distance_mm": 450,
            "illuminance_lux": 1000,
            "time_s": 10,
            "angle_deg": 45,
            "source": "customer cosmetic spec CS-12 rev B",
        },
        "surfaces": [{"face": "bottom", "cosmetic_class": "C"}],
    }


def _brief(base: dict[str, Any], appearance: dict[str, Any]) -> DesignBrief:
    return DesignBrief.model_validate({**base, "appearance": appearance})


def _ux(material: str) -> dict[str, Any]:
    return {
        "system": "ux-creator",
        "cmf": {
            "materials": [{"id": "shell", "name": material}],
            "parts": [{"id": "body", "surface": "case", "material": "shell"}],
        },
    }


def _pinned(
    base: dict[str, Any], tmp_path: Path, payload: object, part: str = "body"
) -> tuple[DesignBrief, Path]:
    path = tmp_path / "kettle.ux.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    appearance = _appearance()
    appearance["cmf"] = {
        "path": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "part": part,
    }
    brief = _brief(base, appearance)
    return brief, path


def _status(brief: DesignBrief, path: Path | None) -> str:
    (check,) = _cmf_checks(brief, path)
    assert check.id == "appearance_cmf"
    return check.status


def test_matching_material_passes(enclosure_brief_dict: dict[str, Any], tmp_path: Path) -> None:
    material = str(enclosure_brief_dict["material"]).lower()
    brief, path = _pinned(enclosure_brief_dict, tmp_path, _ux(material))
    assert resolve_cmf(brief, tmp_path) == path
    assert _status(brief, path) == "pass"


def test_no_cmf_pin_is_not_checked(enclosure_brief_dict: dict[str, Any]) -> None:
    assert _cmf_checks(_brief(enclosure_brief_dict, _appearance()), None) == []


def test_missing_file_is_unknown(enclosure_brief_dict: dict[str, Any], tmp_path: Path) -> None:
    brief, path = _pinned(enclosure_brief_dict, tmp_path, _ux("x"))
    path.unlink()
    assert _status(brief, path) == "unknown"
    assert _status(brief, None) == "unknown"


def test_changed_contract_fails(enclosure_brief_dict: dict[str, Any], tmp_path: Path) -> None:
    brief, path = _pinned(enclosure_brief_dict, tmp_path, _ux(enclosure_brief_dict["material"]))
    path.write_text(json.dumps(_ux("PC")), encoding="utf-8")
    assert _status(brief, path) == "fail"


@pytest.mark.parametrize(
    "payload",
    [
        _ux("PC"),
        {"system": "wire", "cmf": _ux("ABS")["cmf"]},
        {"system": "ux-creator"},
        {"system": "ux-creator", "cmf": {"parts": [{"id": "body", "material": "none"}]}},
        [],
    ],
)
def test_unusable_contract_fails(
    enclosure_brief_dict: dict[str, Any], tmp_path: Path, payload: object
) -> None:
    brief, path = _pinned(enclosure_brief_dict, tmp_path, payload)
    assert _status(brief, path) == "fail"


def test_unknown_part_fails(enclosure_brief_dict: dict[str, Any], tmp_path: Path) -> None:
    ux = _ux(enclosure_brief_dict["material"])
    brief, path = _pinned(enclosure_brief_dict, tmp_path, ux, part="lid")
    assert _status(brief, path) == "fail"


def test_corrupt_json_fails(enclosure_brief_dict: dict[str, Any], tmp_path: Path) -> None:
    brief, path = _pinned(enclosure_brief_dict, tmp_path, _ux("x"))
    path.write_bytes(b"{not json")
    assert brief.appearance is not None and brief.appearance.cmf is not None
    pinned = brief.model_copy(
        update={
            "appearance": brief.appearance.model_copy(
                update={
                    "cmf": brief.appearance.cmf.model_copy(
                        update={"sha256": hashlib.sha256(b"{not json").hexdigest()}
                    )
                }
            )
        }
    )
    assert _status(pinned, path) == "fail"
