# pyright: reportPrivateUsage=false
"""Interchange envelope v3 sidecars on mech's sister exports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mech import _envelope
from mech.appearance import write_appearance
from mech.board_envelope import write_board_envelope
from test_appearance import _appearance, _brief


def test_exports_carry_a_checkable_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enclosure_brief_dict: dict[str, Any]
) -> None:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    brief_path = tmp_path / "demo.brief.json"
    brief_path.write_text("{}\n", encoding="utf-8")
    brief = _brief(enclosure_brief_dict, _appearance())
    for result in (
        write_board_envelope(brief, tmp_path / "out", brief_path),
        write_appearance(brief, tmp_path / "out", brief_path),
    ):
        artifact = Path(result["path"])
        assert result["decision_refs"] == []
        assert _envelope.check_envelope(artifact, "mech", tmp_path, result["sha256"])[0] == "pass"
        brief_path.write_text("{}\n ", encoding="utf-8")
        status, detail = _envelope.check_envelope(artifact, "mech", tmp_path)
        assert (status, "source changed" in detail) == ("fail", True)
        brief_path.unlink()
        assert _envelope.check_envelope(artifact, "mech", tmp_path)[0] == "unknown"
        brief_path.write_text("{}\n", encoding="utf-8")


def test_broken_decision_log_refuses_the_sidecar(tmp_path: Path) -> None:
    artifact = tmp_path / "x.mech-board-envelope.json"
    artifact.write_text("{}\n", encoding="utf-8")
    log = tmp_path / "observations/mech/decisions.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text('{"vrp_version": 2, "event_id": "forged"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        _envelope.write_envelope(artifact, "mech", [], tmp_path)
