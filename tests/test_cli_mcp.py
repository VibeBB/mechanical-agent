from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mech.cli import main


def _write_brief(tmp_path: Path, brief_dict: dict[str, Any]) -> Path:
    path = tmp_path / "demo.brief.json"
    path.write_text(json.dumps(brief_dict), encoding="utf-8")
    return path


def test_cli_doctor(capsys: pytest.CaptureFixture[str]):
    assert main(["doctor"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] in {"pass", "fail"}


def test_cli_author(
    enclosure_brief_dict: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    brief_path = _write_brief(tmp_path, enclosure_brief_dict)
    out_dir = tmp_path / "out"
    rc = main(["author", "--brief", str(brief_path), "--out", str(out_dir)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "pass"
    assert (out_dir / "design-report.json").exists()


def test_cli_author_bad_brief_exits(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    brief_path = tmp_path / "bad.json"
    brief_path.write_text("{broken", encoding="utf-8")
    rc = main(["author", "--brief", str(brief_path), "--out", str(tmp_path / "o")])
    assert rc != 0


def test_cli_gates(
    enclosure_brief_dict: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    brief_path = _write_brief(tmp_path, enclosure_brief_dict)
    out_dir = tmp_path / "out"
    assert main(["export", "--brief", str(brief_path), "--out", str(out_dir)]) == 0
    capsys.readouterr()
    rc = main(["gates", "--brief", str(brief_path), "--out", str(out_dir)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "pass"


def test_cli_export(
    enclosure_brief_dict: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    brief_path = _write_brief(tmp_path, enclosure_brief_dict)
    out_dir = tmp_path / "out"
    rc = main(["export", "--brief", str(brief_path), "--out", str(out_dir)])
    assert rc == 0
    assert any(out_dir.glob("*.step"))


def test_cli_intake(
    enclosure_brief_dict: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    from mech.brief import DesignBrief, brief_sha256

    brief = DesignBrief.model_validate(enclosure_brief_dict)
    brief_path = _write_brief(tmp_path, enclosure_brief_dict)
    intake = {
        "brief_sha256": brief_sha256(brief),
        "requirements": [{"id": "R1", "text": "all", "source": "user", "speaker": "user"}],
        "assumptions": [],
        "open_questions": [],
        "part_sources": {p: ["R1"] for p in brief.part_ids()},
        "feature_sources": {f: ["R1"] for f in brief.feature_ids()},
    }
    intake_path = tmp_path / "i.json"
    intake_path.write_text(json.dumps(intake), encoding="utf-8")
    rc = main(["intake", "--brief", str(brief_path), "--intake", str(intake_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "ready"


def _tool_payload(result: Any) -> Any:
    text = result.content[0].text
    return json.loads(text)


def test_mcp_doctor():
    from mech.mcp_server import call_tool

    result = call_tool("mech_doctor", {})
    assert not result.isError
    payload = _tool_payload(result)
    assert payload["verdict"] in {"pass", "fail"}


def test_mcp_standards_threads():
    from mech.mcp_server import call_tool

    result = call_tool("mech_standards", {"kind": "threads"})
    assert not result.isError
    payload = _tool_payload(result)
    assert "M5" in json.dumps(payload)


def test_mcp_fit_lookup():
    from mech.mcp_server import call_tool

    result = call_tool(
        "mech_fit_lookup",
        {
            "nominal_mm": 20,
            "hole_class": "H7",
            "shaft_class": "g6",
            "intent": "clearance",
        },
    )
    assert not result.isError
    payload = _tool_payload(result)
    assert payload["fit"]["classification"] == "clearance"


def test_mcp_validate_brief(enclosure_brief_dict: dict[str, Any]):
    from mech.mcp_server import call_tool

    result = call_tool("mech_validate_brief", {"brief": enclosure_brief_dict})
    assert not result.isError
    payload = _tool_payload(result)
    assert payload["brief"]["design_type"] == "enclosure"


def test_mcp_unknown_tool_fail_closed():
    from mech.mcp_server import call_tool

    result = call_tool("mech_nonsense", {})
    assert result.isError


def test_mcp_bad_arguments_fail_closed():
    from mech.mcp_server import call_tool

    result = call_tool("mech_validate_brief", {"brief": {"design_type": "x"}})
    assert result.isError


def test_mcp_rejects_paths_outside_workspace(
    enclosure_brief_dict: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    from mech.mcp_server import call_tool

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(workspace))
    traversal = call_tool("mech_render", {"dxf_path": "../outside.dxf"})
    absolute = call_tool(
        "mech_export_envelope",
        {
            "brief": enclosure_brief_dict,
            "out_path": str(tmp_path / "outside.envelope.json"),
        },
    )

    assert traversal.isError
    assert absolute.isError
    assert "outside the workspace" in _tool_payload(traversal)["failure_reason"]
    assert "outside the workspace" in _tool_payload(absolute)["failure_reason"]


def test_mcp_export_envelope_accepts_relative_workspace_path(
    enclosure_brief_dict: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    from mech.mcp_server import call_tool

    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    brief = {
        **enclosure_brief_dict,
        "harness_anchors": [
            {"name": "fixture", "kind": "clip", "position_mm": [0, 0, 0]},
        ],
    }
    result = call_tool(
        "mech_export_envelope",
        {"brief": brief, "out_path": "contracts/demo.envelope.json"},
    )

    assert not result.isError
    assert (tmp_path / "contracts" / "demo.envelope.json").is_file()


def test_mcp_tool_annotations():
    from mech.mcp_server import tool_specs

    write_tools = {
        "mech_author",
        "mech_gates",
        "mech_export_envelope",
        "mech_render",
        "mech_render_views",
        "mech_record_decision",
        "mech_record_impression",
        "mech_record_vision_review",
        "mech_ux_respond",
    }
    tools = tool_specs()
    assert {tool.name for tool in tools} == {
        "mech_doctor",
        "mech_standards",
        "mech_validate_brief",
        "mech_intake",
        "mech_fit_lookup",
        "mech_author",
        "mech_gates",
        "mech_export_envelope",
        "mech_dxf_lint",
        "mech_render",
        "mech_render_views",
        "mech_record_decision",
        "mech_record_impression",
        "mech_record_vision_review",
        "mech_records_status",
        "mech_ux_inbox",
        "mech_ux_respond",
    }
    for tool in tools:
        annotations = tool.annotations
        assert annotations is not None
        assert annotations.title
        assert annotations.readOnlyHint is (tool.name not in write_tools)
        assert annotations.destructiveHint is (tool.name in write_tools)
        assert annotations.idempotentHint is True
        assert annotations.openWorldHint is False
