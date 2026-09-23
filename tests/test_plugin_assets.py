from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "mech"
REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FRONTMATTER = ("name:", "description:")


def test_plugin_manifest():
    data = json.loads((PLUGIN_ROOT / ".plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert data["name"] == "mech"
    assert data["license"] == "BSD-3-Clause"
    assert data["version"]


def test_mcp_config():
    data = json.loads((PLUGIN_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    mech = data["mcpServers"]["mech"]
    assert mech["command"] == "sh"
    assert "mech_launcher.py" in " ".join(mech["args"])
    assert "mcp_server" in " ".join(mech["args"])


def test_hooks_config():
    data = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert set(data) >= {"session_start", "pre_tool_use", "stop", "post_tool_use"}
    for groups in data.values():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["type"] == "command"
                assert hook["command"]


def test_skill_frontmatter():
    skills = sorted((PLUGIN_ROOT / "skills").glob("*/SKILL.md"))
    assert len(skills) >= 5
    for skill in skills:
        head = skill.read_text(encoding="utf-8")[:600]
        for marker in REQUIRED_FRONTMATTER:
            assert marker in head, f"{skill.name} missing {marker}"


def test_brief_rule_is_path_triggered():
    head = (PLUGIN_ROOT / "skills" / "mech-brief-rules" / "SKILL.md").read_text(encoding="utf-8")[
        :600
    ]
    assert "paths:" in head
    assert "triggers:" not in head


def test_agent_definitions():
    agents = sorted((PLUGIN_ROOT / "agents").glob("*.md"))
    assert {a.stem for a in agents} == {
        "mech-brief",
        "mech-design",
        "mech-review",
    }


def test_commands():
    commands = {c.stem for c in (PLUGIN_ROOT / "commands").glob("*.md")}
    assert commands >= {"design", "doctor", "gates", "export"}


def _hook_env() -> dict[str, str]:
    env = dict(os.environ)
    env["MECH_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    return env


def test_protect_generated_blocks_step(tmp_path: Path):
    script = PLUGIN_ROOT / "hooks" / "scripts" / "protect_generated.py"
    payload = json.dumps(
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "write", "path": str(tmp_path / "x.step")},
        }
    )
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=payload,
        capture_output=True,
        text=True,
        env=_hook_env(),
        check=False,
    )
    assert proc.returncode == 2


def test_protect_generated_allows_readonly(tmp_path: Path):
    script = PLUGIN_ROOT / "hooks" / "scripts" / "protect_generated.py"
    payload = json.dumps(
        {
            "tool_name": "terminal",
            "tool_input": {"command": f"grep foo {tmp_path}/x.step"},
        }
    )
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=payload,
        capture_output=True,
        text=True,
        env=_hook_env(),
        check=False,
    )
    assert proc.returncode == 0


def test_protect_generated_allows_brief(tmp_path: Path):
    script = PLUGIN_ROOT / "hooks" / "scripts" / "protect_generated.py"
    payload = json.dumps(
        {
            "tool_name": "file_editor",
            "tool_input": {"command": "write", "path": str(tmp_path / "d.brief.json")},
        }
    )
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=payload,
        capture_output=True,
        text=True,
        env=_hook_env(),
        check=False,
    )
    assert proc.returncode == 0


def test_report_design_status_no_output(tmp_path: Path):
    script = PLUGIN_ROOT / "hooks" / "scripts" / "report_design_status.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        input="{}",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=_hook_env(),
        check=False,
    )
    assert proc.returncode == 0


def test_report_design_status_reads_report(tmp_path: Path):
    script = PLUGIN_ROOT / "hooks" / "scripts" / "report_design_status.py"
    report = {
        "schema_version": 1,
        "verdict": "pass",
        "checks": [{"id": "x", "status": "pass", "subject": "s"}],
        "summary": {"pass": 1, "fail": 0, "unknown": 0},
    }
    (tmp_path / "design-report.json").write_text(json.dumps(report), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(script)],
        input="{}",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=_hook_env(),
        check=False,
    )
    assert proc.returncode == 0
    assert "pass" in proc.stdout.lower() or "design" in proc.stdout.lower()


def test_launcher_resolves(tmp_path: Path):
    launcher = PLUGIN_ROOT / "scripts" / "mech_launcher.py"
    proc = subprocess.run(
        [sys.executable, str(launcher), "doctor"],
        capture_output=True,
        text=True,
        env=_hook_env(),
        check=False,
    )
    # doctor verdict is pass/fail JSON or a resolution error; must be JSON
    assert proc.stdout.strip().startswith("{")
