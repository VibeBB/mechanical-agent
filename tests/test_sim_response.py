from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from mech.brief import DesignBrief
from mech.gates import _sim_ruggedness_checks  # pyright: ignore[reportPrivateUsage]
from mech.sim_request import write_sim_request
from mech.sim_response import expected_request, resolve_response, ruggedness_findings

MATERIAL = {"youngs_mpa": 18600, "poisson": 0.12, "density_kg_m3": 1850, "component_mass_g": 20}
RUGGED = {
    "board_material": MATERIAL,
    "vibration": {
        "psd_g2_hz": 0.04,
        "min_fn_hz": 200,
        "parts": [
            {
                "ref": "U1",
                "x_mm": 0,
                "y_mm": 0,
                "length_mm": 20,
                "parallel_to": "width",
                "steinberg_c": 1.0,
            }
        ],
    },
    "drop": {"height_mm": 1000, "pulse_ms": 1, "restitution": 0.5, "max_shock_g": 1500},
    "response_path": "sim/demo.ruggedness.sim-response.json",
}
PASSING = [
    {"id": "ruggedness.vibration.fn", "verdict": "pass", "measured": 412.0, "limit": "≥ 200 Hz"},
    {"id": "ruggedness.drop.peak_g", "verdict": "pass", "measured": 900.0, "limit": "≤ 1500 g"},
]


def _brief(base: dict[str, Any], **changes: Any) -> DesignBrief:
    rugged = {**RUGGED, **changes}
    return DesignBrief.model_validate(
        {**base, "enclosure": {**base["enclosure"], "ruggedness": rugged}}
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _answer(
    root: Path,
    brief: DesignBrief,
    checks: list[dict[str, Any]],
    *,
    status: str | None = None,
    verdict: str | None = None,
    report_verdict: str | None = None,
    **overrides: Any,
) -> Path:
    """Play simulation-agent: write request (mech), report and response (sim)."""
    out = write_sim_request(brief, root / "sim", root=root)
    request_path = Path(out["request"])
    rows: list[dict[str, Any]] = [
        {"analysis": "ruggedness", "detail": "", "evidence": [], **c} for c in checks
    ]
    aggregate = (
        "fail"
        if any(c["verdict"] == "fail" for c in rows)
        else "unknown"
        if any(c["verdict"] == "unknown" for c in rows)
        else "pass"
    )
    verdict = verdict or aggregate
    report = root / "out" / f"{brief.name}-ruggedness" / "sim-report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps({"schema_version": 1, "verdict": report_verdict or verdict, "checks": rows}),
        encoding="utf-8",
    )
    response: dict[str, Any] = {
        "schema_version": 2,
        "request_id": out["request_id"],
        "request_sha256": _sha(request_path),
        "brief_sha256": out["sim_brief_sha256"],
        "status": status
        or {"pass": "accepted", "fail": "rejected", "unknown": "needs_info"}[verdict],
        "verdict": verdict,
        "report_path": str(report),
        "sha256": _sha(report),
        "decision_refs": [],
        "reasons": [],
        **overrides,
    }
    path = root / "sim" / "demo.ruggedness.sim-response.json"
    path.write_text(json.dumps(response), encoding="utf-8")
    return path


def _status(brief: DesignBrief, path: Path | None, root: Path) -> dict[str, str]:
    return {subject: status for subject, status, _, _ in ruggedness_findings(brief, path, root)}


def test_accepted_response_reports_sim_checks(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    brief = _brief(enclosure_brief_dict)
    path = _answer(tmp_path, brief, PASSING)
    findings = ruggedness_findings(brief, path, tmp_path)
    assert [(s, v) for s, v, _, _ in findings] == [
        ("response", "pass"),
        ("vibration.fn", "pass"),
        ("drop.peak_g", "pass"),
    ]
    assert findings[1][2] == 412.0
    assert "limit ≥ 200 Hz" in findings[1][3]
    checks = _sim_ruggedness_checks(brief, path, tmp_path)
    assert {c.id for c in checks} == {"sim_ruggedness"}
    assert all(c.status == "pass" for c in checks)


def test_rejected_response_keeps_the_failing_sim_check(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    brief = _brief(enclosure_brief_dict)
    failing = [PASSING[0], {**PASSING[1], "verdict": "fail", "measured": 1800.0}]
    path = _answer(tmp_path, brief, failing)
    assert _status(brief, path, tmp_path) == {
        "response": "pass",
        "vibration.fn": "pass",
        "drop.peak_g": "fail",
    }


@pytest.mark.parametrize("status", ["needs_info", "deferred"])
def test_unanswered_response_is_unknown(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any], status: str
) -> None:
    brief = _brief(enclosure_brief_dict)
    path = _answer(
        tmp_path, brief, PASSING, status=status, verdict="unknown", reasons=["needs a test"]
    )
    findings = ruggedness_findings(brief, path, tmp_path)
    assert [(s, v) for s, v, _, _ in findings] == [("response", "unknown")]
    assert "needs a test" in findings[0][3]


def test_no_ruggedness_means_no_checks(enclosure_brief: DesignBrief, tmp_path: Path) -> None:
    assert ruggedness_findings(enclosure_brief, None, tmp_path) == []
    assert resolve_response(enclosure_brief, tmp_path) is None


def test_missing_or_unset_response_is_unknown(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    unset = _brief(enclosure_brief_dict, response_path=None)
    assert _status(unset, None, tmp_path) == {"response": "unknown"}
    brief = _brief(enclosure_brief_dict)
    path = resolve_response(brief, tmp_path)
    assert path == tmp_path / "sim" / "demo.ruggedness.sim-response.json"
    assert _status(brief, path, tmp_path) == {"response": "unknown"}
    assert _status(brief, tmp_path / "x.json", tmp_path) == {"response": "unknown"}


def test_stale_brief_fails(tmp_path: Path, enclosure_brief_dict: dict[str, Any]) -> None:
    path = _answer(tmp_path, _brief(enclosure_brief_dict), PASSING)
    changed = _brief(
        enclosure_brief_dict,
        drop={"height_mm": 1200, "pulse_ms": 1, "restitution": 0.5, "max_shock_g": 1500},
    )
    findings = ruggedness_findings(changed, path, tmp_path)
    assert [(s, v) for s, v, _, _ in findings] == [("response", "fail")]
    assert expected_request(changed)[0] in findings[0][3]


def test_response_path_does_not_change_the_request(enclosure_brief_dict: dict[str, Any]) -> None:
    moved = _brief(
        enclosure_brief_dict, response_path="elsewhere/demo.ruggedness.sim-response.json"
    )
    assert expected_request(moved) == expected_request(_brief(enclosure_brief_dict))


def test_tampered_request_or_report_fails(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    brief = _brief(enclosure_brief_dict)
    path = _answer(tmp_path, brief, PASSING)
    request = tmp_path / "sim" / "demo.ruggedness.sim-request.json"
    request.write_text(request.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert _status(brief, path, tmp_path) == {"response": "fail"}
    path = _answer(tmp_path, brief, PASSING)
    report = tmp_path / "out" / "demo-ruggedness" / "sim-report.json"
    report.write_text(report.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert _status(brief, path, tmp_path) == {"report": "fail"}


def test_missing_request_or_report_is_unknown(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    brief = _brief(enclosure_brief_dict)
    path = _answer(tmp_path, brief, PASSING)
    (tmp_path / "out" / "demo-ruggedness" / "sim-report.json").unlink()
    assert _status(brief, path, tmp_path) == {"report": "unknown"}
    (tmp_path / "sim" / "demo.ruggedness.sim-request.json").unlink()
    assert _status(brief, path, tmp_path) == {"response": "unknown"}


def test_report_outside_workspace_is_unknown(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    root = tmp_path / "ws"
    brief = _brief(enclosure_brief_dict)
    path = _answer(root, brief, PASSING)
    outside = tmp_path / "sim-report.json"
    outside.write_text("{}", encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**data, "report_path": str(outside)}), encoding="utf-8")
    assert _status(brief, path, root) == {"report": "unknown"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "accepted", "verdict": "fail"},
        {"status": "rejected", "verdict": "pass"},
        {"sha256": None},
        {"schema_version": 1},
        {"extra": True},
        {"request_sha256": "not-a-hash"},
    ],
)
def test_malformed_response_is_unknown(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any], overrides: dict[str, Any]
) -> None:
    brief = _brief(enclosure_brief_dict)
    path = _answer(tmp_path, brief, PASSING)
    data = {**json.loads(path.read_text(encoding="utf-8")), **overrides}
    path.write_text(json.dumps({k: v for k, v in data.items() if v is not None}), encoding="utf-8")
    assert _status(brief, path, tmp_path) == {"response": "unknown"}


def test_other_requester_or_kind_fails(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    brief = _brief(enclosure_brief_dict)
    path = _answer(tmp_path, brief, PASSING)
    request = tmp_path / "sim" / "demo.ruggedness.sim-request.json"
    data = json.loads(request.read_text(encoding="utf-8"))
    request.write_text(json.dumps({**data, "kind": "thermal"}), encoding="utf-8")
    response = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**response, "request_sha256": _sha(request)}), encoding="utf-8")
    assert _status(brief, path, tmp_path) == {"response": "fail"}


@pytest.mark.parametrize(
    ("checks", "report_verdict", "expected"),
    [
        ([], None, {"report": "unknown"}),
        ([{"id": "thermal.tj", "verdict": "pass"}], None, {"report": "unknown"}),
        ([{"id": "ruggedness.drop.peak_g", "verdict": "maybe"}], "pass", {"report": "unknown"}),
        (PASSING, "fail", {"report": "fail"}),
    ],
)
def test_unusable_report_fails_closed(
    tmp_path: Path,
    enclosure_brief_dict: dict[str, Any],
    checks: list[dict[str, Any]],
    report_verdict: str | None,
    expected: dict[str, str],
) -> None:
    brief = _brief(enclosure_brief_dict)
    path = _answer(tmp_path, brief, checks, verdict="pass", report_verdict=report_verdict)
    assert _status(brief, path, tmp_path) == expected


def test_non_finite_measurement_is_dropped(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    brief = _brief(enclosure_brief_dict)
    path = _answer(tmp_path, brief, [{**PASSING[0], "measured": True}])
    assert ruggedness_findings(brief, path, tmp_path)[1][2] is None


def test_failing_sim_check_carries_margin_and_guidance(
    tmp_path: Path, enclosure_brief_dict: dict[str, Any]
) -> None:
    brief = _brief(enclosure_brief_dict)
    failing = [
        PASSING[0],
        {
            **PASSING[1],
            "verdict": "fail",
            "measured": 1800.0,
            "margin": -300.0,
            "guidance": ["pulse_ms ≥ 1.2 (cushioning; peak ∝ 1/pulse)", 7],
        },
    ]
    path = _answer(tmp_path, brief, failing)
    drop = next(f for f in ruggedness_findings(brief, path, tmp_path) if f[0] == "drop.peak_g")
    assert drop[1] == "fail"
    assert "margin -300" in drop[3]
    assert drop[3].endswith("fix: pulse_ms ≥ 1.2 (cushioning; peak ∝ 1/pulse)")
