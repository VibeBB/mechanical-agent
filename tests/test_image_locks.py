from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "update_image_digest_lock.py"
PRINTER = ROOT / "scripts" / "print_locked_image.py"


def _update_args(lock: Path, tools: Path) -> list[str]:
    return [
        sys.executable,
        str(UPDATER),
        "--lock",
        str(lock),
        "--entry",
        "mech_tools",
        "--image",
        "ghcr.io/vibebb/mech-tools",
        "--tag",
        f"{'a' * 40}-tools",
        "--digest",
        f"sha256:{'b' * 64}",
        "--published-at",
        "2026-05-05T12:00:00Z",
        "--workflow-run",
        "https://github.com/VibeBB/mechanical-agent/actions/runs/1",
        "--dockerfile",
        "docker/mech-tools.Dockerfile",
        "--tools-json",
        str(tools),
        "--attestation",
        "https://github.com/VibeBB/mechanical-agent/attestations/1",
    ]


def test_attested_lock_is_supported_by_writer_and_reader(tmp_path: Path) -> None:
    lock = tmp_path / "image-digests.json"
    tools = tmp_path / "tools.json"
    tools.write_text(json.dumps({"python": "3.12"}), encoding="utf-8")

    updated = subprocess.run(
        _update_args(lock, tools),
        capture_output=True,
        check=False,
        text=True,
    )
    assert updated.returncode == 0, updated.stdout + updated.stderr
    assert updated.stdout.strip() == "UPDATED"
    assert json.loads(lock.read_text(encoding="utf-8"))["mech_tools"]["attestation"] == (
        "https://github.com/VibeBB/mechanical-agent/attestations/1"
    )

    printed = subprocess.run(
        [
            sys.executable,
            str(PRINTER),
            "--lock",
            str(lock),
            "--entry",
            "mech_tools",
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert printed.returncode == 0, printed.stdout + printed.stderr
    assert printed.stdout.strip() == f"ghcr.io/vibebb/mech-tools@sha256:{'b' * 64}"

    unchanged = subprocess.run(
        _update_args(lock, tools),
        capture_output=True,
        check=False,
        text=True,
    )
    assert unchanged.returncode == 0, unchanged.stdout + unchanged.stderr
    assert unchanged.stdout.strip() == "UNCHANGED"


def test_writer_rejects_non_https_attestation(tmp_path: Path) -> None:
    lock = tmp_path / "image-digests.json"
    tools = tmp_path / "tools.json"
    tools.write_text(json.dumps({"python": "3.12"}), encoding="utf-8")
    args = _update_args(lock, tools)
    args[-1] = "file:///tmp/attestation"

    result = subprocess.run(
        args,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert "attestation must be an HTTPS URL" in result.stdout
