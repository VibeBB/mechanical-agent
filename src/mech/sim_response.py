"""Read simulation-agent's hash-bound answer to a mech ruggedness request."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .brief import DesignBrief
from .sim_request import ruggedness_brief
from .workspace import workspace_path

CheckStatus = Literal["pass", "fail", "unknown"]
Finding = tuple[str, CheckStatus, float | None, str]

_REQUEST_SUFFIX = ".sim-request.json"
_RESPONSE_SUFFIX = ".sim-response.json"
_PREFIX = "ruggedness."


class SimResponse(BaseModel):
    """Mirror of simulation-agent's ``SimulationResponse`` (schema v2)."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: Literal[2]
    request_id: str = Field(min_length=1)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    brief_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    status: Literal["accepted", "rejected", "deferred", "needs_info"]
    verdict: Literal["pass", "fail", "unknown"] | None = None
    report_path: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    decision_refs: list[str] = Field(default_factory=list[str])
    reasons: list[str] = Field(default_factory=list[str])

    @model_validator(mode="after")
    def validate_verdict(self) -> SimResponse:
        if self.status == "accepted" and self.verdict != "pass":
            raise ValueError("accepted responses require a pass verdict")
        if self.status == "rejected" and self.verdict != "fail":
            raise ValueError("rejected responses require a fail verdict")
        if (self.report_path is None) != (self.sha256 is None):
            raise ValueError("report_path and sha256 must be provided together")
        if self.status in ("accepted", "rejected") and self.report_path is None:
            raise ValueError("accepted and rejected responses require a hashed report")
        return self


def expected_request(brief: DesignBrief) -> tuple[str, str]:
    """``(request_id, sim brief sha256)`` the current brief would request."""
    text = json.dumps(ruggedness_brief(brief), indent=2, sort_keys=True) + "\n"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{brief.name}-ruggedness-{digest[:12]}", digest


def resolve_response(brief: DesignBrief, base_dir: Path, *, confine: bool = False) -> Path | None:
    """Path of ``enclosure.ruggedness.response_path``; ``confine`` keeps MCP reads inside."""
    spec = brief.enclosure
    rugged = spec.ruggedness if spec is not None else None
    if rugged is None or rugged.response_path is None:
        return None
    if confine:
        return workspace_path(rugged.response_path, root=base_dir)
    candidate = Path(rugged.response_path)
    return candidate if candidate.is_absolute() else base_dir / candidate


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    if path.is_symlink():
        raise ValueError(f"{path.name} is a symlink")
    return json.loads(path.read_text(encoding="utf-8"))


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def _report_findings(report: Any, response: SimResponse) -> list[Finding]:
    if not isinstance(report, dict):
        return [("report", "unknown", None, "sim report is not a JSON object")]
    data: dict[str, Any] = report  # pyright: ignore[reportUnknownVariableType]
    raw_checks: Any = data.get("checks")
    if not isinstance(raw_checks, list):
        return [("report", "unknown", None, "sim report has no checks list")]
    findings: list[Finding] = []
    for raw in raw_checks:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(raw, dict):
            return [("report", "unknown", None, "sim report check is not an object")]
        item: dict[str, Any] = raw  # pyright: ignore[reportUnknownVariableType]
        check_id, verdict = item.get("id"), item.get("verdict")
        if not isinstance(check_id, str) or not check_id.startswith(_PREFIX):
            continue
        if verdict not in ("pass", "fail", "unknown"):
            return [("report", "unknown", None, f"{check_id} has no pass/fail/unknown verdict")]
        detail = str(item.get("detail") or "")
        limit = item.get("limit")
        if limit is not None:
            detail = f"{detail}; limit {limit}" if detail else f"limit {limit}"
        margin = _number(item.get("margin"))
        if margin is not None:
            detail = f"{detail}; margin {margin:.6g}"
        guidance: object = item.get("guidance")
        if isinstance(guidance, list):
            fixes = [str(line) for line in guidance if isinstance(line, str)]  # pyright: ignore[reportUnknownVariableType]
            if fixes:
                detail = f"{detail}; fix: {' | '.join(fixes)}"
        measured = _number(item.get("measured"))
        findings.append((check_id.removeprefix(_PREFIX), verdict, measured, detail))
    if not findings:
        return [("report", "unknown", None, "sim report has no ruggedness checks")]
    if data.get("verdict") != response.verdict:
        return [
            (
                "report",
                "fail",
                None,
                f"report verdict {data.get('verdict')!r} != response verdict {response.verdict!r}",
            )
        ]
    return findings


def ruggedness_findings(
    brief: DesignBrief, response_path: Path | None, root: Path
) -> list[Finding]:
    """``(subject, status, measured, detail)`` per ruggedness result; fail-closed.

    The response must answer the request the *current* brief would emit
    (request id and sim brief sha256), the sibling request file must match
    ``request_sha256``, and the hashed report must be unchanged. Only
    simulation's own check verdicts are reported; mech adds no judgement.
    """
    spec = brief.enclosure
    if spec is None or spec.ruggedness is None:
        return []
    if response_path is None:
        return [("response", "unknown", None, "enclosure.ruggedness.response_path is not set")]
    if not response_path.name.endswith(_RESPONSE_SUFFIX):
        return [("response", "unknown", None, f"not a {_RESPONSE_SUFFIX}: {response_path.name}")]
    if not response_path.is_file():
        return [("response", "unknown", None, f"simulation response missing: {response_path}")]
    try:
        response = SimResponse.model_validate(_load_json(response_path))
    except (OSError, ValueError, ValidationError) as exc:
        return [("response", "unknown", None, f"invalid simulation response: {exc}")]
    request_path = response_path.with_name(
        response_path.name.removesuffix(_RESPONSE_SUFFIX) + _REQUEST_SUFFIX
    )
    if not request_path.is_file() or request_path.is_symlink():
        return [("response", "unknown", None, f"request missing beside response: {request_path}")]
    if _sha256(request_path) != response.request_sha256:
        return [("response", "fail", None, "stale: request file changed after the response")]
    try:
        request = _load_json(request_path)
    except (OSError, ValueError) as exc:
        return [("response", "unknown", None, f"invalid request: {exc}")]
    expected_id, expected_sha = expected_request(brief)
    if not isinstance(request, dict) or (
        request.get("from_system"),  # pyright: ignore[reportUnknownMemberType]
        request.get("kind"),  # pyright: ignore[reportUnknownMemberType]
        request.get("request_id"),  # pyright: ignore[reportUnknownMemberType]
    ) != ("mech", "ruggedness", response.request_id):
        return [("response", "fail", None, "response does not answer a mech ruggedness request")]
    if response.request_id != expected_id or response.brief_sha256 != expected_sha:
        return [
            (
                "response",
                "fail",
                None,
                f"stale: answers {response.request_id}, current brief requests {expected_id}",
            )
        ]
    if response.status in ("needs_info", "deferred"):
        reasons = "; ".join(response.reasons) or "no reason given"
        return [("response", "unknown", None, f"simulation {response.status}: {reasons}")]
    assert response.report_path is not None and response.sha256 is not None
    try:
        report_path = workspace_path(response.report_path, root=root)
    except ValueError as exc:
        return [("report", "unknown", None, str(exc))]
    if not report_path.is_file():
        return [("report", "unknown", None, f"hashed sim report missing: {response.report_path}")]
    if _sha256(report_path) != response.sha256:
        return [("report", "fail", None, "stale: sim report changed after the response")]
    try:
        report = _load_json(report_path)
    except (OSError, ValueError) as exc:
        return [("report", "unknown", None, f"invalid sim report: {exc}")]
    findings = _report_findings(report, response)
    if findings[0][0] == "report":
        return findings
    return [("response", "pass", None, f"{response.request_id} {response.status}"), *findings]


__all__ = ["SimResponse", "expected_request", "resolve_response", "ruggedness_findings"]
