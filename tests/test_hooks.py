"""Tests for the mech plugin hook scripts."""

import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HOOKS = Path(__file__).parents[1] / "plugins" / "mech" / "hooks" / "scripts"
PROTECT_SCRIPT = HOOKS / "protect_generated.py"
STATUS_SCRIPT = HOOKS / "report_design_status.py"
VISION_SCRIPT = HOOKS / "record_vision_tool_event.py"
OBSERVE_SCRIPT = HOOKS / "record_image_observation.py"

_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c626001000000ffff03000006000557bfabd40000000049"
    "454e44ae426082"
)


def _run_hook(script: Path, payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("OPENHANDS_PROJECT_DIR", None)
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _run_protect(payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    return _run_hook(PROTECT_SCRIPT, payload)


def test_protect_denies_artifact_writes() -> None:
    for payload in (
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "create", "path": "out/enclosure.step"},
        },
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "str_replace", "path": "out/part.stl"},
        },
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "insert", "path": "out/part.3mf"},
        },
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "write", "file_path": "out/drawing.dxf"},
        },
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "write", "path": "out/manifest.json"},
        },
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "edit", "path": "out/provenance.json"},
        },
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "write", "path": "out/design-report.json"},
        },
        {
            "tool_name": "apply_patch",
            "tool_input": {"patch": "+++ b/out/casing.step"},
        },
    ):
        result = _run_protect(payload)
        assert result.returncode == 2, payload
        assert "projections of the brief" in result.stderr


def test_protect_allows_reads_and_unprotected_writes() -> None:
    for payload in (
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "view", "path": "out/enclosure.step"},
        },
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "read", "path": "out/design-report.json"},
        },
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "write", "path": "briefs/enclosure.brief.json"},
        },
        {
            "tool_name": "terminal",
            "tool_input": {"command": "python -m mech author --brief b.brief.json"},
        },
    ):
        assert _run_protect(payload).returncode == 0, payload


def test_protect_denies_terminal_artifact_writes() -> None:
    for command in (
        "echo x > out.step",
        "echo x >> out.stl",
        "cat a | tee out.3mf",
        "cp template out.dxf",
        "mv draft.step final.step",
        "dd of=out.step",
        "sed -i s/a/b/ out.stl",
        "touch out.step",
        "rm out/provenance.json",
        "rm out/design-report.json",
        "python3 gen.py && cp x out.step",
        "cmd 2> err.dxf",
        "sudo rm manifest.json",
        "env FOO=1 rm out.step",
    ):
        payload = {"tool_name": "terminal", "tool_input": {"command": command}}
        assert _run_protect(payload).returncode == 2, command


def test_protect_allows_terminal_reads_and_content_mentions() -> None:
    for command in (
        "cat out.step",
        "grep -r verdict out/design-report.json",
        "find . -name '*.step'",
        "ls -la out/",
        "cp out.step backups/out.bak",
        "tar czf artifacts.tgz out/part.stl",
        "echo 'see out/enclosure.step' > notes.md",
        "echo '.step is a format' > README.md",
        "cmd >&2",
        "cmd 2>&1 | grep out.step",
        "sha256sum manifest.json",
    ):
        payload = {"tool_name": "terminal", "tool_input": {"command": command}}
        assert _run_protect(payload).returncode == 0, command


def test_protect_scans_paths_not_file_bodies() -> None:
    for payload in (
        {
            "tool_name": "file_editor",
            "tool_input": {
                "command": "create",
                "path": "docs/notes.md",
                "file_text": "outputs include .step, .stl and design-report.json",
            },
        },
        {
            "tool_name": "file_editor",
            "tool_input": {
                "command": "str_replace",
                "path": "AGENTS.md",
                "old_str": "a",
                "new_str": "provenance.json is generated",
            },
        },
    ):
        assert _run_protect(payload).returncode == 0


def test_protect_rejects_malformed_input() -> None:
    result = subprocess.run(
        [sys.executable, str(PROTECT_SCRIPT)],
        input="{not-json",
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "invalid hook input" in result.stderr


def _write_report(path: Path, verdict: str, checks: list[dict[str, Any]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": 1,
        "verdict": verdict,
        "checks": checks or [],
        "summary": {"pass": 0, "fail": 0, "unknown": 0},
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def _run_status(working_dir: Path) -> subprocess.CompletedProcess[str]:
    return _run_hook(STATUS_SCRIPT, {"working_dir": str(working_dir)})


def test_report_design_status_pass_and_fail(tmp_path: Path) -> None:
    _write_report(tmp_path / "enclosure" / "design-report.json", "pass")
    _write_report(
        tmp_path / "bracket" / "design-report.json",
        "fail",
        checks=[
            {"id": "dfm.wall", "status": "fail", "subject": "wall"},
            {"id": "fits.FT1", "status": "unknown", "subject": "fit"},
            {"id": "export.step", "status": "pass", "subject": "export"},
        ],
    )

    result = _run_status(tmp_path)

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["decision"] == "allow"
    context = output["additionalContext"]
    assert "verdict=pass" in context
    assert "verdict=fail" in context
    assert "state each failing gate explicitly" in context
    assert "dfm.wall" in context
    assert "fits.FT1" in context
    assert "export.step" not in context


def test_report_design_status_none(tmp_path: Path) -> None:
    result = _run_status(tmp_path)

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["decision"] == "allow"
    assert "No design reports found" in output["additionalContext"]


def test_report_design_status_skips_nested_and_hidden_paths(tmp_path: Path) -> None:
    _write_report(tmp_path / "a" / "b" / "c" / "d" / "e" / "design-report.json", "fail")
    _write_report(tmp_path / ".venv" / "x" / "design-report.json", "fail")

    result = _run_status(tmp_path)

    assert result.returncode == 0
    assert "No design reports found" in json.loads(result.stdout)["additionalContext"]


def test_report_design_status_malformed(tmp_path: Path) -> None:
    report = tmp_path / "design-report.json"
    report.write_text("{not-json", encoding="utf-8")

    result = _run_status(tmp_path)

    assert result.returncode == 1
    assert "report_design_status:" in result.stderr


def test_report_design_status_missing_verdict(tmp_path: Path) -> None:
    report = tmp_path / "design-report.json"
    report.write_text(json.dumps({"checks": []}), encoding="utf-8")

    result = _run_status(tmp_path)

    assert result.returncode == 1
    assert "report_design_status:" in result.stderr


def _run_vision(payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    return _run_hook(VISION_SCRIPT, payload)


def _vision_events(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / "observations" / "mech" / "vision-tool-events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_record_vision_tool_event_appends(tmp_path: Path) -> None:
    payload = {
        "working_dir": str(tmp_path),
        "session_id": "session-1",
        "tool_name": "inspect_image_with_vision",
        "tool_input": {"image_index": 0, "question": "Check wall thickness"},
        "tool_response": {
            "answer": "Walls look uniform.",
            "profile_name": "vision",
            "model": "vision-model-1",
        },
    }

    assert _run_vision(payload).returncode == 0
    assert _run_vision(payload).returncode == 0

    events = _vision_events(tmp_path)
    assert len(events) == 2
    first, second = events
    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert first["tool_name"] == "inspect_image_with_vision"
    assert first["image_index"] == 0
    assert first["question"] == "Check wall thickness"
    assert first["profile_name"] == "vision"
    assert first["model"] == "vision-model-1"
    assert first["response_sha256"].startswith("sha256:")
    assert first["session_id"] == "session-1"
    assert first["event_id"]
    assert first["event_id"] != second["event_id"]


def test_record_vision_tool_event_ignores_other_tools_and_errors(tmp_path: Path) -> None:
    for payload in (
        {
            "working_dir": str(tmp_path),
            "tool_name": "mech_render",
            "tool_input": {},
            "tool_response": {"answer": "ok", "profile_name": "vision", "model": "m"},
        },
        {
            "working_dir": str(tmp_path),
            "tool_name": "inspect_image_with_vision",
            "tool_input": {"image_index": 0},
            "tool_response": {"error": "vision profile missing"},
        },
        {
            "working_dir": str(tmp_path),
            "tool_name": "inspect_image_with_vision",
            "tool_input": {"image_index": 0},
            "tool_response": {"is_error": True, "answer": "x", "profile_name": "v", "model": "m"},
        },
        {
            "working_dir": str(tmp_path),
            "tool_name": "inspect_image_with_vision",
            "tool_input": {"image_index": 0},
            "tool_response": {"answer": "", "profile_name": "v", "model": "m"},
        },
        {
            "working_dir": str(tmp_path),
            "tool_name": "inspect_image_with_vision",
            "tool_input": {"image_index": 0},
            "tool_response": {"answer": "ok", "profile_name": "", "model": "m"},
        },
        {
            "working_dir": str(tmp_path),
            "tool_name": "inspect_image_with_vision",
            "tool_input": {"image_index": 0},
            "tool_response": {"answer": "ok"},
        },
    ):
        assert _run_vision(payload).returncode == 0
    assert _vision_events(tmp_path) == []


def _run_observe(payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    return _run_hook(OBSERVE_SCRIPT, payload)


def _observations(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / "observations" / "mech" / "image-observations.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_record_image_observation_logs_file_editor_view(tmp_path: Path) -> None:
    image = tmp_path / "renders" / "enclosure.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(_PNG)
    payload = {
        "working_dir": str(tmp_path),
        "tool_name": "file_editor",
        "tool_input": {"command": "view", "path": str(image)},
        "tool_response": {"output": "ok"},
        "session_id": "s1",
    }

    assert _run_observe(payload).returncode == 0

    records = _observations(tmp_path)
    assert len(records) == 1
    assert records[0]["tool_name"] == "file_editor"
    assert records[0]["image_path"] == str(image)
    assert records[0]["image_sha256"] == hashlib.sha256(_PNG).hexdigest()
    assert records[0]["sequence"] == 1
    assert records[0]["session_id"] == "s1"
    assert records[0]["event_id"]


def test_record_image_observation_logs_render_paths(tmp_path: Path) -> None:
    image = tmp_path / "out" / "enclosure" / "render.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(_PNG)
    payload = {
        "working_dir": str(tmp_path),
        "tool_name": "mech_render",
        "tool_input": {"brief_path": "b.brief.json"},
        "tool_response": {
            "content": [
                {"type": "text", "text": json.dumps({"output_path": str(image)})},
                {"type": "image", "data": "...", "mimeType": "image/png"},
            ]
        },
        "session_id": "s2",
    }

    assert _run_observe(payload).returncode == 0

    records = _observations(tmp_path)
    assert len(records) == 1
    assert records[0]["tool_name"] == "mech_render"
    assert records[0]["image_path"] == str(image)
    assert records[0]["image_sha256"] == hashlib.sha256(_PNG).hexdigest()


def test_record_image_observation_skips_non_images_and_errors(tmp_path: Path) -> None:
    image = tmp_path / "render.png"
    image.write_bytes(_PNG)
    for payload in (
        {
            "working_dir": str(tmp_path),
            "tool_name": "file_editor",
            "tool_input": {"command": "create", "path": str(image)},
            "tool_response": {"output": "ok"},
        },
        {
            "working_dir": str(tmp_path),
            "tool_name": "file_editor",
            "tool_input": {"command": "view", "path": str(tmp_path / "missing.png")},
            "tool_response": {"output": "ok"},
        },
        {
            "working_dir": str(tmp_path),
            "tool_name": "file_editor",
            "tool_input": {"command": "view", "path": str(tmp_path / "notes.txt")},
            "tool_response": {"output": "ok"},
        },
        {
            "working_dir": str(tmp_path),
            "tool_name": "mech_render",
            "tool_input": {},
            "tool_response": {"error": "build123d missing"},
        },
        {
            "working_dir": str(tmp_path),
            "tool_name": "mech_render",
            "tool_input": {},
            "tool_response": {
                "content": [{"type": "text", "text": '{"output_path": "/no/such.png"}'}]
            },
        },
        {
            "working_dir": str(tmp_path),
            "tool_name": "terminal",
            "tool_input": {"command": "view render.png"},
            "tool_response": {"output": "ok"},
        },
    ):
        assert _run_observe(payload).returncode == 0
    assert _observations(tmp_path) == []


def test_hook_scripts_return_zero_on_malformed_stdin() -> None:
    for script in (VISION_SCRIPT, OBSERVE_SCRIPT, STATUS_SCRIPT):
        result = subprocess.run(
            [sys.executable, str(script)],
            input="{not-json",
            text=True,
            capture_output=True,
            check=False,
        )
        # The recorders fail open on malformed input; the status reporter
        # fails closed so a broken event can never look like a clean stop.
        expected = 1 if script == STATUS_SCRIPT else 0
        assert result.returncode == expected, script.name


ATTACH_SCRIPT = HOOKS / "intake_attachments.py"


def _write_event(events: Path, name: str, source: str, urls: list[str]) -> None:
    event = {
        "id": name,
        "source": source,
        "llm_message": {
            "role": "user",
            "content": (
                [{"type": "image", "image_urls": urls}]
                if urls
                else [{"type": "text", "text": "hi"}]
            ),
        },
    }
    (events / name).write_text(json.dumps(event), encoding="utf-8")


def _run_attach_hook(
    payload: dict[str, Any], events_dir: Path | None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if events_dir is not None:
        env["MECH_AGENT_EVENTS_DIR"] = str(events_dir)
    else:
        env.pop("MECH_AGENT_EVENTS_DIR", None)
    return subprocess.run(
        [sys.executable, str(ATTACH_SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_intake_attachments_materializes_user_images(tmp_path: Path) -> None:
    events = tmp_path / "events"
    events.mkdir()
    encoded = "data:image/png;base64," + base64.b64encode(_PNG).decode()
    _write_event(events, "event-1.json", "user", [encoded])
    _write_event(events, "event-2.json", "agent", [encoded])
    _write_event(events, "event-3.json", "user", [])
    workdir = tmp_path / "work"
    workdir.mkdir()

    payload = {"working_dir": str(workdir)}
    result = _run_attach_hook(payload, events)

    assert result.returncode == 0
    attachments = workdir / "intake" / "attachments"
    images = list(attachments.glob("*.png"))
    assert len(images) == 1
    assert images[0].read_bytes() == _PNG
    records = [
        json.loads(line)
        for line in (attachments / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["sha256"] == hashlib.sha256(_PNG).hexdigest()
    assert records[0]["materialized"] is True
    # second run is a no-op
    assert _run_attach_hook(payload, events).returncode == 0
    assert len(list(attachments.glob("*.png"))) == 1
    assert len((attachments / "manifest.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_intake_attachments_records_non_data_urls(tmp_path: Path) -> None:
    events = tmp_path / "events"
    events.mkdir()
    _write_event(events, "event-1.json", "user", ["https://example.com/board.png"])
    workdir = tmp_path / "work"
    workdir.mkdir()

    result = _run_attach_hook({"working_dir": str(workdir)}, events)

    assert result.returncode == 0
    manifest = workdir / "intake" / "attachments" / "manifest.jsonl"
    record = json.loads(manifest.read_text(encoding="utf-8").splitlines()[0])
    assert record["materialized"] is False
    assert record["reason"] == "non-data-url"


def test_intake_attachments_fails_open_without_events_dir(tmp_path: Path) -> None:
    result = _run_attach_hook({"working_dir": str(tmp_path)}, None)
    assert result.returncode == 0
    assert not (tmp_path / "intake").exists()


def test_intake_attachments_uses_session_default_path(tmp_path: Path) -> None:
    home = tmp_path / "home"
    events = home / ".openhands" / "agent-canvas" / "dev_conversations" / "session-9" / "events"
    events.mkdir(parents=True)
    encoded = "data:image/png;base64," + base64.b64encode(_PNG).decode()
    _write_event(events, "event-1.json", "user", [encoded])
    workdir = tmp_path / "work"
    workdir.mkdir()

    env = dict(os.environ)
    env.pop("MECH_AGENT_EVENTS_DIR", None)
    env["HOME"] = str(home)
    result = subprocess.run(
        [sys.executable, str(ATTACH_SCRIPT)],
        input=json.dumps({"working_dir": str(workdir), "session_id": "session-9"}),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert list((workdir / "intake" / "attachments").glob("*.png"))
