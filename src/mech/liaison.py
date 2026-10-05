"""Sister Liaison Protocol (SLP) v2 — mech side.

UX-creator directs the whole VibeBB family through request/response files
in the workspace ``liaison/`` directory: ``<id>.ux-request.json`` written
by UX-creator, ``<id>.ux-response.json`` written by the target sister.
This module is a local strict mirror of the v2 contracts — it never
imports UX-creator code — and powers ``mech_ux_inbox`` / ``mech_ux_respond``
and the ``ux inbox`` / ``ux respond`` CLI.

Request states (inbox): ``stale`` > ``answered`` > ``blocked`` > ``new``.

* ``stale`` — an input file is missing or its current sha256 differs
  from the request, or an existing response's ``input_hashes`` no longer
  match the current input bytes.
* ``answered`` — a valid response by responder ``mech`` exists.
* ``blocked`` — a ``depends_on`` id has no valid response file (of any
  responder) or the request sits on a dependency cycle among visible
  requests.
* ``new`` — everything else.

Malformed request files are reported separately; valid requests aimed at
other targets are skipped silently.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from .records import RECORDS_DIR, sha256_file, tree_sha256
from .workspace import workspace_path, workspace_root

TARGET: str = "mech"
LIAISON_DIR = Path("liaison")

_TARGETS = {
    "bard",
    "circuit",
    "dashboard",
    "doc",
    "firmware",
    "fpga",
    "mech",
    "prodeng",
    "sim",
    "wire",
}

_SHA256 = r"^[0-9a-f]{64}$"
_SLUG = r"^[a-z0-9][a-z0-9._-]{0,63}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RequestInput(_Strict):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256)


class UXRequestV2(_Strict):
    """Local strict mirror of the UX-creator liaison request v2."""

    schema_version: Literal[2] = 2
    system: Literal["ux-creator"] = "ux-creator"
    id: str = Field(pattern=_SLUG)
    target_agent: str = Field(min_length=1)
    stage: Literal[
        "requirements",
        "design",
        "manufacturing_handoff",
        "build",
        "evaluation",
        "revision",
    ]
    risk: Literal["low", "high"]
    purpose: str = Field(min_length=20)
    rationale: str = ""
    requested_changes: list[str] = Field(min_length=1)
    inputs: list[RequestInput] = Field(default_factory=list[RequestInput])
    expected_deliverables: list[str] = Field(min_length=1)
    acceptance: list[str] = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list[str])
    created_at: str = Field(min_length=1)

    @field_validator("target_agent")
    @classmethod
    def _target_known(cls, value: str) -> str:
        if value not in _TARGETS:
            raise ValueError(f"unknown target_agent: {value}")
        return value

    @model_validator(mode="after")
    def _high_risk_cites_job(self) -> UXRequestV2:
        if self.risk == "high" and not re.search(
            r"ux[-_a-z0-9]*job[-_a-z0-9]*", self.rationale, re.IGNORECASE
        ):
            raise ValueError("high-risk requests must cite a UX job id in rationale")
        return self


class GateVerdict(_Strict):
    gate: str = Field(min_length=1)
    verdict: Literal["pass", "fail", "unknown"]


class UXResponseV2(_Strict):
    """Local strict mirror of the UX-creator liaison response v2."""

    schema_version: Literal[2] = 2
    system: Literal["ux-creator"] = "ux-creator"
    request: str = Field(pattern=_SLUG)
    responder: str = Field(min_length=1)
    status: Literal["accepted", "in_progress", "done", "rejected", "deferred", "needs_info"]
    reason: str = ""
    input_hashes: dict[str, str] = Field(default_factory=dict[str, str])
    artifacts: list[RequestInput] = Field(default_factory=list[RequestInput])
    gate_verdicts: list[GateVerdict] = Field(default_factory=list[GateVerdict])
    decision_refs: list[str] = Field(default_factory=list[str])
    impression_refs: list[str] = Field(default_factory=list[str])
    questions_for_user: list[str] = Field(default_factory=list[str])
    responded_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def _reason_length(self) -> UXResponseV2:
        if self.status not in ("accepted", "in_progress") and len(self.reason) < 20:
            raise ValueError(
                "reason needs at least 20 characters unless status is accepted/in_progress"
            )
        return self


class RespondPayload(_Strict):
    """What the agent supplies to ``ux_respond``."""

    request: str = Field(pattern=_SLUG)
    status: Literal["accepted", "in_progress", "done", "rejected", "deferred", "needs_info"]
    reason: str = ""
    artifacts: list[str] = Field(default_factory=list[str])
    gate_verdicts: list[GateVerdict] = Field(default_factory=list[GateVerdict])
    design_reports: list[str] = Field(default_factory=list[str])
    decision_refs: list[str] = Field(default_factory=list[str])
    impression_refs: list[str] = Field(default_factory=list[str])
    questions_for_user: list[str] = Field(default_factory=list[str])


def liaison_dir(root: Path | None = None) -> Path:
    return (root or workspace_root()).resolve() / LIAISON_DIR


def _load_request(path: Path) -> tuple[UXRequestV2 | None, str | None]:
    """Parse one request file; (model, error)."""
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"unparseable: {exc}"
    try:
        request = UXRequestV2.model_validate(raw)
    except ValidationError as exc:
        # valid JSON that does not validate may still name a target
        target: Any = (
            cast(dict[str, Any], raw).get("target_agent") if isinstance(raw, dict) else None
        )
        if target == TARGET:
            return None, f"invalid request: {exc.errors()[0].get('msg', exc)}"
        return None, None
    if request.id != path.stem.removesuffix(".ux-request"):
        return (
            (None, f"id {request.id!r} != file stem")
            if request.target_agent == TARGET
            else (None, None)
        )
    if request.target_agent != TARGET:
        return None, None
    return request, None


def _load_response(path: Path, request_id: str) -> tuple[UXResponseV2 | None, str | None]:
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"unparseable: {exc}"
    try:
        response = UXResponseV2.model_validate(raw)
    except ValidationError as exc:
        return None, f"invalid response: {exc.errors()[0].get('msg', exc)}"
    if response.request != request_id:
        return None, f"response.request {response.request!r} != {request_id!r}"
    return response, None


def _current_input_hashes(request: UXRequestV2, root: Path) -> tuple[dict[str, str], str | None]:
    """sha256 of each request input as it stands; error when unreadable."""
    hashes: dict[str, str] = {}
    for item in request.inputs:
        try:
            path = workspace_path(item.path, root)
        except ValueError:
            return {}, f"input outside workspace: {item.path}"
        if not path.is_file():
            return {}, f"input missing: {item.path}"
        hashes[item.path] = sha256_file(path)
    return hashes, None


def _is_stale(
    request: UXRequestV2,
    current: dict[str, str],
    input_error: str | None,
    response: UXResponseV2 | None,
) -> bool:
    if input_error is not None:
        return True
    for item in request.inputs:
        if current.get(item.path) != item.sha256:
            return True
    return response is not None and response.input_hashes != current


def _responded_ids(requests: dict[str, UXRequestV2], root: Path) -> set[str]:
    """Request ids (any target) with a valid sibling response file."""
    answered: set[str] = set()
    directory = liaison_dir(root)
    for request_file in directory.glob("*.ux-request.json"):
        request_id = request_file.name.removesuffix(".ux-request.json")
        response_path = directory / f"{request_id}.ux-response.json"
        if not response_path.is_file():
            continue
        response, error = _load_response(response_path, request_id)
        if response is not None and error is None:
            answered.add(request_id)
    return answered


def _blocked(request: UXRequestV2, requests: dict[str, UXRequestV2], answered: set[str]) -> bool:
    def on_cycle(rid: str, chain: frozenset[str]) -> bool:
        if rid == request.id and chain:
            return True
        next_request = requests.get(rid)
        if next_request is None or rid in chain:
            return False
        return any(on_cycle(dep, chain | {rid}) for dep in next_request.depends_on)

    if on_cycle(request.id, frozenset()):
        return True
    return any(dep not in answered for dep in request.depends_on)


def ux_inbox(root: Path | None = None) -> dict[str, Any]:
    """List liaison requests targeting mech with their state."""
    base = (root or workspace_root()).resolve()
    directory = liaison_dir(base)
    requests: dict[str, UXRequestV2] = {}
    malformed: list[dict[str, str]] = []
    if directory.is_dir():
        for request_file in sorted(directory.glob("*.ux-request.json")):
            request, error = _load_request(request_file)
            if error is not None:
                malformed.append({"path": str(request_file), "error": error})
            if request is not None:
                requests[request.id] = request
    answered = _responded_ids(requests, base)
    entries: list[dict[str, Any]] = []
    for request_id in sorted(requests):
        request = requests[request_id]
        response_path = directory / f"{request.id}.ux-response.json"
        response: UXResponseV2 | None = None
        response_error: str | None = None
        if response_path.is_file():
            response, response_error = _load_response(response_path, request.id)
            if response_error is not None:
                malformed.append({"path": str(response_path), "error": response_error})
            elif response is not None and response.responder != TARGET:
                response = None
        current, input_error = _current_input_hashes(request, base)
        if _is_stale(request, current, input_error, response):
            state = "stale"
        elif response is not None:
            state = "answered"
        elif _blocked(request, requests, answered):
            state = "blocked"
        else:
            state = "new"
        entries.append(
            {
                "id": request.id,
                "path": str(directory / f"{request.id}.ux-request.json"),
                "stage": request.stage,
                "risk": request.risk,
                "state": state,
                "reasons": [],
                "depends_on": list(request.depends_on),
            }
        )
    return {
        "verdict": "pass",
        "liaison_dir": str(directory),
        "requests": entries,
        "malformed": malformed,
    }


def _event_ids(log: Path) -> set[str]:
    ids: set[str] = set()
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value: Any = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict):
                continue
            record = cast(dict[str, Any], value)
            if isinstance(record.get("event_id"), str):
                ids.add(record["event_id"])
    return ids


def _design_report_verdicts(report_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Derive gate_verdicts entries from a design-report.json."""
    try:
        report = cast(dict[str, Any], json.loads(report_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read design report {report_path}: {exc}") from exc
    name = report_path.stem
    verdict: Any = report.get("verdict")
    verdicts: list[dict[str, str]] = [
        {
            "gate": f"{name}/verdict",
            "verdict": verdict if verdict in ("pass", "fail", "unknown") else "unknown",
        }
    ]
    checks: Any = report.get("checks")
    for entry in cast(list[Any], checks or []):
        if not isinstance(entry, dict):
            continue
        check = cast(dict[str, Any], entry)
        status: Any = check.get("status")
        if status not in (None, "pass"):
            verdicts.append(
                {
                    "gate": f"{name}/{check.get('id', 'check')}",
                    "verdict": status if status in ("fail", "unknown") else "unknown",
                }
            )
    return [str(report_path)], verdicts


def ux_respond(payload: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """Validate and write `liaison/<id>.ux-response.json` for a mech request."""
    base = (root or workspace_root()).resolve()
    try:
        respond = RespondPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid response payload: {exc}") from exc
    directory = liaison_dir(base)
    request_path = directory / f"{respond.request}.ux-request.json"
    if not request_path.is_file():
        raise ValueError(f"no liaison request: {request_path}")
    request, error = _load_request(request_path)
    if request is None or error is not None:
        raise ValueError(f"request {respond.request} is not a valid mech request: {error}")
    current, input_error = _current_input_hashes(request, base)

    artifacts: list[dict[str, str]] = []
    gate_verdicts = [g.model_dump(mode="json") for g in respond.gate_verdicts]
    for value in respond.artifacts:
        path = workspace_path(value, base)
        if not path.exists():
            raise ValueError(f"artifact does not exist: {value}")
        relative = path.relative_to(base).as_posix() if path != base else "."
        artifacts.append({"path": relative, "sha256": tree_sha256(path)})
    for report_value in respond.design_reports:
        report_path = workspace_path(report_value, base)
        if not report_path.is_file():
            raise ValueError(f"design report does not exist: {report_value}")
        relative = report_path.relative_to(base).as_posix()
        _, derived = _design_report_verdicts(report_path)
        artifacts.append({"path": relative, "sha256": tree_sha256(report_path)})
        gate_verdicts.extend(derived)

    if respond.status == "done":
        bad = [g for g in gate_verdicts if g["verdict"] in ("fail", "unknown")]
        if bad:
            names = ", ".join(g["gate"] for g in bad)
            raise ValueError(
                f"status 'done' with fail/unknown gate verdict(s) ({names}); "
                "change status to needs_info or rejected with a reason"
            )
        if not gate_verdicts:
            raise ValueError("status 'done' needs at least one gate verdict")
        if not artifacts:
            raise ValueError("status 'done' needs at least one artifact")
        if _is_stale(request, current, input_error, None):
            raise ValueError(
                "status 'done' while the request is stale; answer with the current inputs"
            )
        if not respond.decision_refs:
            raise ValueError("status 'done' needs at least one decision_ref")
        if not respond.impression_refs:
            raise ValueError("status 'done' needs at least one impression_ref")

    records = base / RECORDS_DIR
    decision_ids = _event_ids(records / "decisions.jsonl")
    for ref in respond.decision_refs:
        if ref not in decision_ids:
            raise ValueError(f"decision_ref not an event_id in decisions.jsonl: {ref}")
    impression_ids = _event_ids(records / "impressions.jsonl") | _event_ids(
        records / "vision-reviews.jsonl"
    )
    for ref in respond.impression_refs:
        if ref not in impression_ids:
            raise ValueError(f"impression_ref not found in impressions/vision-reviews logs: {ref}")

    if respond.status not in ("accepted", "in_progress") and len(respond.reason) < 20:
        raise ValueError(
            "reason needs at least 20 characters unless status is accepted/in_progress"
        )

    from datetime import UTC, datetime

    response = UXResponseV2(
        request=request.id,
        responder=TARGET,
        status=respond.status,
        reason=respond.reason,
        input_hashes=current,
        artifacts=[RequestInput.model_validate(a) for a in artifacts],
        gate_verdicts=[GateVerdict.model_validate(g) for g in gate_verdicts],
        decision_refs=list(respond.decision_refs),
        impression_refs=list(respond.impression_refs),
        questions_for_user=list(respond.questions_for_user),
        responded_at=datetime.now(UTC).isoformat(),
    )
    out_path = directory / f"{request.id}.ux-response.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        response.model_dump_json(indent=2, exclude_defaults=False) + "\n",
        encoding="utf-8",
    )
    return {"verdict": "pass", "response": str(out_path), "status": respond.status}
