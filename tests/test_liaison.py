"""SLP v2 liaison: inbox states, malformed files, ux_respond refusals."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from mech import liaison, records

HOOK = Path(__file__).parents[1] / "plugins" / "mech" / "hooks" / "scripts" / "report_ux_inbox.py"

IMPRESSION = (
    "The views sheet reads cleanly: every face of the enclosure projects "
    "without stray edges and the hidden-line layer separates clearly from "
    "the outlines. What worries me is the lid recess, which is easy to "
    "misread at this scale. A maker could fixture from the front view "
    "alone, and the anchor crosses sit exactly where the brief declared "
    "them. Next I would render the lid's own DXF and compare the snap "
    "relief against the measured deflection."
)


def _request(rid: str, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 2,
        "system": "ux-creator",
        "id": rid,
        "target_agent": "mech",
        "stage": "design",
        "risk": "low",
        "purpose": "Produce an enclosure design consistent with the UX job",
        "rationale": "",
        "requested_changes": ["author the enclosure"],
        "inputs": [],
        "expected_deliverables": ["design-report.json"],
        "acceptance": ["gates pass"],
        "depends_on": [],
        "created_at": "2026-10-05T00:00:00+00:00",
    }
    return base | over


def _write_request(root: Path, rid: str, **over: Any) -> Path:
    directory = root / "liaison"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{rid}.ux-request.json"
    path.write_text(json.dumps(_request(rid, **over)), encoding="utf-8")
    return path


def _input(root: Path, name: str, content: bytes = b"in") -> dict[str, str]:
    path = root / name
    path.write_bytes(content)
    return {"path": name, "sha256": records.sha256_file(path)}


def _respond_payload(rid: str, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "request": rid,
        "status": "accepted",
        "reason": "",
        "artifacts": [],
        "gate_verdicts": [],
        "design_reports": [],
        "decision_refs": [],
        "impression_refs": [],
        "questions_for_user": [],
    }
    return base | over


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("OPENHANDS_PROJECT_DIR", str(tmp_path))
    return tmp_path


def test_inbox_new_and_skips_other_targets(ws: Path) -> None:
    _write_request(ws, "req-a")
    _write_request(ws, "req-b", target_agent="wire")
    out = liaison.ux_inbox()
    assert [r["id"] for r in out["requests"]] == ["req-a"]
    assert out["requests"][0]["state"] == "new"
    assert out["malformed"] == []


def test_inbox_stale_when_input_changes(ws: Path) -> None:
    ref = _input(ws, "spec.txt", b"v1")
    _write_request(ws, "req-s", inputs=[ref])
    (ws / "spec.txt").write_bytes(b"v2")
    out = liaison.ux_inbox()
    assert out["requests"][0]["state"] == "stale"


def test_inbox_stale_when_input_missing(ws: Path) -> None:
    _write_request(ws, "req-m", inputs=[{"path": "gone.txt", "sha256": "0" * 64}])
    out = liaison.ux_inbox()
    assert out["requests"][0]["state"] == "stale"


def test_inbox_answered_and_stale_response(ws: Path) -> None:
    ref = _input(ws, "spec.txt")
    _write_request(ws, "req-r", inputs=[ref])
    assert liaison.ux_respond(_respond_payload("req-r", status="accepted"))["verdict"] == "pass"
    out = liaison.ux_inbox()
    assert out["requests"][0]["state"] == "answered"
    (ws / "spec.txt").write_bytes(b"changed")
    out = liaison.ux_inbox()
    assert out["requests"][0]["state"] == "stale"


def test_inbox_blocked_and_cycle(ws: Path) -> None:
    _write_request(ws, "req-dep", depends_on=["req-other"])
    out = liaison.ux_inbox()
    assert out["requests"][0]["state"] == "blocked"
    # a request the dep depends on lives in the workspace targeting wire: still blocked
    _write_request(ws, "req-other", target_agent="wire")
    out = liaison.ux_inbox()
    assert out["requests"][0]["state"] == "blocked"
    # answer req-other as wire → unblocks req-dep
    (ws / "liaison" / "req-other.ux-response.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "system": "ux-creator",
                "request": "req-other",
                "responder": "wire",
                "status": "accepted",
                "reason": "",
                "input_hashes": {},
                "artifacts": [],
                "gate_verdicts": [],
                "decision_refs": [],
                "impression_refs": [],
                "questions_for_user": [],
                "responded_at": "2026-10-05T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    assert liaison.ux_inbox()["requests"][0]["state"] == "new"
    # cycle between two mech requests blocks both
    _write_request(ws, "cyc-a", depends_on=["cyc-b"])
    _write_request(ws, "cyc-b", depends_on=["cyc-a"])
    out = {r["id"]: r["state"] for r in liaison.ux_inbox()["requests"]}
    assert out["cyc-a"] == "blocked" and out["cyc-b"] == "blocked"


def test_inbox_malformed(ws: Path) -> None:
    directory = ws / "liaison"
    directory.mkdir()
    (directory / "bad.ux-request.json").write_text("{nope", encoding="utf-8")
    (directory / "inv.ux-request.json").write_text(
        json.dumps(_request("different-id")), encoding="utf-8"
    )
    (directory / "schema.ux-request.json").write_text(
        json.dumps(_request("schema") | {"purpose": "short"}), encoding="utf-8"
    )
    (directory / "other.ux-request.json").write_text(
        json.dumps(_request("other", target_agent="wire") | {"purpose": "x"}),
        encoding="utf-8",
    )
    out = liaison.ux_inbox()
    paths = {Path(m["path"]).name for m in out["malformed"]}
    assert paths == {"bad.ux-request.json", "inv.ux-request.json", "schema.ux-request.json"}
    assert out["requests"] == []


def test_inbox_malformed_response(ws: Path) -> None:
    _write_request(ws, "req-x")
    (ws / "liaison" / "req-x.ux-response.json").write_text("{bad", encoding="utf-8")
    out = liaison.ux_inbox()
    assert out["requests"][0]["state"] == "new"
    assert Path(out["malformed"][0]["path"]).name == "req-x.ux-response.json"


def _decision_event(ws: Path) -> str:
    artifact = ws / "out"
    artifact.mkdir(exist_ok=True)
    (artifact / "a.step").write_bytes(b"s")
    result = records.record_decision(
        {
            "id": "closure-type",
            "stage": "design",
            "question": "Which closure type should the enclosure lid use?",
            "principles": [
                "Snap-fit strain stays below the material allowable strain",
                "Fastener torque is bounded by boss strip strength",
            ],
            "options": [
                {"name": "snap", "pros": ["no hardware"], "cons": ["strain risk"]},
                {"name": "screws", "pros": ["serviceable"], "cons": ["extra parts"]},
            ],
            "chosen": "snap",
            "rationale": (
                "The snap beam deflection at engagement stays under 60% of the "
                "allowable strain for the chosen resin, so the closure needs no "
                "metal hardware, the part count stays minimal, and the tooling "
                "cost of an undercut screw boss disappears entirely."
            ),
            "evidence": [{"path": "out"}],
            "risks": ["snap fatigue over repeated openings"],
            "revisit_when": "drop or fatigue testing shows a crack",
        }
    )
    return str(result["record"]["event_id"])


def test_ux_respond_done_full(ws: Path) -> None:
    ref = _input(ws, "spec.txt")
    _write_request(ws, "req-done", inputs=[ref])
    decision = _decision_event(ws)
    impression = records.record_impression(
        {"stage": "design", "artifacts": ["out"], "impression": IMPRESSION}
    )["record"]["event_id"]
    (ws / "out" / "design-report.json").write_text(
        json.dumps(
            {
                "verdict": "pass",
                "checks": [
                    {"id": "dfm.wall", "status": "pass"},
                    {"id": "fits.FT1", "status": "fail"},
                ],
            }
        ),
        encoding="utf-8",
    )
    # a fail verdict inside a design report forces refusal of 'done'
    with pytest.raises(ValueError, match="fail/unknown"):
        liaison.ux_respond(
            _respond_payload(
                "req-done",
                status="done",
                reason="finished the enclosure design iteration",
                design_reports=["out/design-report.json"],
                decision_refs=[decision],
                impression_refs=[str(impression)],
            )
        )
    (ws / "out" / "design-report.json").write_text(
        json.dumps({"verdict": "pass", "checks": [{"id": "dfm.wall", "status": "pass"}]}),
        encoding="utf-8",
    )
    out = liaison.ux_respond(
        _respond_payload(
            "req-done",
            status="done",
            reason="finished the enclosure design iteration",
            design_reports=["out/design-report.json"],
            decision_refs=[decision],
            impression_refs=[str(impression)],
        )
    )
    assert out["verdict"] == "pass"
    response = json.loads((ws / "liaison" / "req-done.ux-response.json").read_text())
    assert response["status"] == "done"
    assert response["responder"] == "mech"
    assert response["input_hashes"] == {"spec.txt": ref["sha256"]}
    assert {g["gate"] for g in response["gate_verdicts"]} == {"design-report/verdict"}
    assert response["decision_refs"] == [decision]
    assert liaison.ux_inbox()["requests"][0]["state"] == "answered"


def test_ux_respond_refusals(ws: Path) -> None:
    _write_request(ws, "req-r")
    (ws / "spec.txt").write_bytes(b"x")
    with pytest.raises(ValueError, match="no liaison request"):
        liaison.ux_respond(_respond_payload("missing"))
    with pytest.raises(ValueError, match="gate verdict"):
        liaison.ux_respond(
            _respond_payload(
                "req-r",
                status="done",
                reason="r" * 25,
                gate_verdicts=[{"gate": "g", "verdict": "fail"}],
                artifacts=["spec.txt"],
                decision_refs=["x"],
                impression_refs=["y"],
            )
        )
    with pytest.raises(ValueError, match="at least one gate"):
        liaison.ux_respond(
            _respond_payload("req-r", status="done", reason="r" * 25, artifacts=["spec.txt"])
        )
    with pytest.raises(ValueError, match="at least one artifact"):
        liaison.ux_respond(
            _respond_payload(
                "req-r",
                status="done",
                reason="r" * 25,
                gate_verdicts=[{"gate": "g", "verdict": "pass"}],
            )
        )
    with pytest.raises(ValueError, match="decision_ref"):
        liaison.ux_respond(
            _respond_payload(
                "req-r",
                status="done",
                reason="r" * 25,
                artifacts=["spec.txt"],
                gate_verdicts=[{"gate": "g", "verdict": "pass"}],
                impression_refs=["y"],
            )
        )
    with pytest.raises(ValueError, match="impression_ref"):
        liaison.ux_respond(
            _respond_payload(
                "req-r",
                status="done",
                reason="r" * 25,
                artifacts=["spec.txt"],
                gate_verdicts=[{"gate": "g", "verdict": "pass"}],
                decision_refs=[_decision_event(ws)],
            )
        )
    with pytest.raises(ValueError, match="not an event_id"):
        liaison.ux_respond(
            _respond_payload("req-r", status="in_progress", reason="r" * 25, decision_refs=["nope"])
        )
    with pytest.raises(ValueError, match="not found"):
        liaison.ux_respond(
            _respond_payload(
                "req-r",
                status="in_progress",
                reason="r" * 25,
                decision_refs=[_decision_event(ws)],
                impression_refs=["nope"],
            )
        )
    with pytest.raises(ValueError, match="20 characters"):
        liaison.ux_respond(_respond_payload("req-r", status="rejected", reason="too short"))
    # accepted/in_progress allow a short reason
    assert liaison.ux_respond(_respond_payload("req-r", status="in_progress"))["verdict"] == "pass"
    # overwrite allowed
    assert liaison.ux_respond(_respond_payload("req-r", status="accepted"))["verdict"] == "pass"


def test_ux_respond_done_stale_request(ws: Path) -> None:
    ref = _input(ws, "spec.txt")
    _write_request(ws, "req-stale", inputs=[ref])
    (ws / "spec.txt").write_bytes(b"changed")
    (ws / "out").mkdir()
    (ws / "out" / "a.step").write_bytes(b"s")
    decision = _decision_event(ws)
    impression = records.record_impression(
        {"stage": "design", "artifacts": ["out"], "impression": IMPRESSION}
    )["record"]["event_id"]
    with pytest.raises(ValueError, match="stale"):
        liaison.ux_respond(
            _respond_payload(
                "req-stale",
                status="done",
                reason="r" * 25,
                artifacts=["out"],
                gate_verdicts=[{"gate": "g", "verdict": "pass"}],
                decision_refs=[decision],
                impression_refs=[str(impression)],
            )
        )


def test_report_ux_inbox_hook(ws: Path) -> None:
    import os

    def run(root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"working_dir": str(root)}),
            text=True,
            capture_output=True,
            check=False,
            env={k: v for k, v in os.environ.items() if k != "OPENHANDS_PROJECT_DIR"},
        )

    silent = run(ws)
    assert silent.returncode == 0 and silent.stdout.strip() == ""
    _write_request(ws, "pend-1")
    _write_request(ws, "pend-wire", target_agent="wire")
    result = run(ws)
    assert result.returncode == 0
    context = json.loads(result.stdout)["additionalContext"]
    assert "pend-1" in context and "pend-wire" not in context
    assert "mech_ux_inbox" in context
    liaison.ux_respond(_respond_payload("pend-1", status="accepted"))
    assert run(ws).stdout.strip() == ""
