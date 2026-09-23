"""Envelope contract export tests (ADR-0003 wire boundary)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from mech.brief import DesignBrief
from mech.cli import main
from mech.envelope import envelope_source, write_envelope

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "upstream" / "housing.envelope.json"
_ANCHOR_KINDS = {"clip", "grommet", "breakout", "other"}


def _with_anchors(brief_dict: dict[str, Any]) -> dict[str, Any]:
    data = dict(brief_dict)
    data["harness_anchors"] = [
        {"name": "clip-01", "kind": "clip", "position_mm": [100.0, 0.0, 40.0]},
        {"name": "clip-02", "kind": "clip", "position_mm": [180.0, 0.0, 40.0]},
        {"name": "breakout-01", "kind": "breakout", "position_mm": [140.0, 55.0, 10.0]},
    ]
    return data


def _assert_envelope_shape(payload: dict[str, Any]) -> None:
    """Structural mirror of wire's EnvelopeSource (schema_version 1)."""
    assert set(payload) == {"schema_version", "system", "anchors"}
    assert payload["schema_version"] == 1
    assert payload["system"] == "mech"
    assert payload["anchors"], "envelope needs at least one anchor"
    for anchor in payload["anchors"]:
        assert set(anchor) <= {"name", "kind", "position_mm"}
        assert anchor["name"]
        assert anchor["kind"] in _ANCHOR_KINDS
        if "position_mm" in anchor:
            assert len(anchor["position_mm"]) == 3


def test_envelope_source_payload(enclosure_brief_dict: dict[str, Any]) -> None:
    brief = DesignBrief.model_validate(_with_anchors(enclosure_brief_dict))
    payload = envelope_source(brief)
    _assert_envelope_shape(payload)
    anchors = cast("list[dict[str, Any]]", payload["anchors"])
    assert [a["name"] for a in anchors] == [
        "clip-01",
        "clip-02",
        "breakout-01",
    ]


def test_envelope_without_anchors_fails(enclosure_brief_dict: dict[str, Any]) -> None:
    brief = DesignBrief.model_validate(enclosure_brief_dict)
    with pytest.raises(ValueError, match="harness_anchors"):
        envelope_source(brief)


def test_duplicate_anchor_names_rejected(enclosure_brief_dict: dict[str, Any]) -> None:
    data = _with_anchors(enclosure_brief_dict)
    data["harness_anchors"].append(dict(data["harness_anchors"][0]))
    with pytest.raises(ValueError, match="unique"):
        DesignBrief.model_validate(data)


def test_cli_export_envelope(
    enclosure_brief_dict: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    brief_path = tmp_path / "enclosure.brief.json"
    brief_path.write_text(json.dumps(_with_anchors(enclosure_brief_dict)), encoding="utf-8")
    out_path = tmp_path / "enclosure.envelope.json"
    rc = main(["export-envelope", "--brief", str(brief_path), "--out", str(out_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "pass"
    _assert_envelope_shape(json.loads(out_path.read_text(encoding="utf-8")))


def test_cli_export_envelope_empty_fails(
    enclosure_brief_dict: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    brief_path = tmp_path / "enclosure.brief.json"
    brief_path.write_text(json.dumps(enclosure_brief_dict), encoding="utf-8")
    rc = main(
        [
            "export-envelope",
            "--brief",
            str(brief_path),
            "--out",
            str(tmp_path / "enclosure.envelope.json"),
        ]
    )
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "fail"
    assert out["stage"] == "export-envelope"


def test_upstream_fixture_matches_schema() -> None:
    """The golden wire fixture stays EnvelopeSource-shaped."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    _assert_envelope_shape(payload)


def test_doctor_warn_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor", "--warn"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "verdict" in out


def test_write_envelope_roundtrip(enclosure_brief_dict: dict[str, Any], tmp_path: Path) -> None:
    brief = DesignBrief.model_validate(_with_anchors(enclosure_brief_dict))
    out_path = write_envelope(brief, tmp_path / "x.envelope.json")
    _assert_envelope_shape(json.loads(out_path.read_text(encoding="utf-8")))
