"""Conversation provenance checks for design briefs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .brief import DesignBrief, brief_sha256


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^R[0-9]+$")
    text: str = Field(min_length=1)
    source: Literal["user", "agent"]
    speaker: str = Field(min_length=1)


class EvidenceRef(BaseModel):
    """Provenance binding to an intake evidence file (image, document, CAD file).

    `path` resolves relative to the intake file's directory when not absolute.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["image", "document", "cad_file"]
    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    note: str = Field(default="")


class Assumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^A[0-9]+$")
    text: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    evidence: EvidenceRef | None = None


class OpenQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^Q[0-9]+$")
    text: str = Field(min_length=1)
    evidence: EvidenceRef | None = None


class Intake(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requirements: list[Requirement] = Field(min_length=1)
    assumptions: list[Assumption] = Field(default_factory=list[Assumption])
    open_questions: list[OpenQuestion] = Field(default_factory=list[OpenQuestion])
    part_sources: dict[str, list[str]]
    feature_sources: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])

    @model_validator(mode="after")
    def validate_ids_and_sources(self) -> Intake:
        records = [*self.requirements, *self.assumptions, *self.open_questions]
        ids = [record.id for record in records]
        if len(set(ids)) != len(ids):
            raise ValueError("intake ids must be unique")
        for mapping_name, mapping in (
            ("part_sources", self.part_sources),
            ("feature_sources", self.feature_sources),
        ):
            for key, sources in mapping.items():
                if not sources:
                    raise ValueError(f"{mapping_name}[{key}] must not be empty")
        return self


class IntakeReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief_path: Path
    intake_path: Path
    brief_sha256: str
    intake_sha256: str
    sha_matches: bool
    unmapped_parts: list[str]
    unmapped_features: list[str]
    unknown_parts: list[str]
    unknown_features: list[str]
    unknown_sources: dict[str, list[str]]
    assumption_only_parts: list[str]
    assumption_only_features: list[str]
    open_questions: list[OpenQuestion]
    evidence_errors: list[str]
    verdict: Literal["ready", "blocked"]
    reasons: list[str]


def load_intake(path: Path) -> Intake:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load intake {path}: {exc}") from exc
    return Intake.model_validate(value)


def intake_sha256(intake: Intake) -> str:
    return hashlib.sha256(intake.model_dump_json().encode("utf-8")).hexdigest()


def check_intake(
    brief: DesignBrief,
    intake: Intake,
    brief_path: Path,
    intake_path: Path,
) -> IntakeReport:
    """Fail-closed provenance gate between the brief and its intake sidecar."""
    expected = brief_sha256(brief)
    sha_matches = intake.brief_sha256 == expected

    part_ids = brief.part_ids()
    feature_ids = brief.feature_ids()
    source_ids = (
        {r.id for r in intake.requirements}
        | {a.id for a in intake.assumptions}
        | {q.id for q in intake.open_questions}
    )

    unmapped_parts = [p for p in part_ids if p not in intake.part_sources]
    unmapped_features = [f for f in feature_ids if f not in intake.feature_sources]
    unknown_parts = [p for p in intake.part_sources if p not in part_ids]
    unknown_features = [f for f in intake.feature_sources if f not in feature_ids]

    unknown_sources: dict[str, list[str]] = {}
    for mapping, name in (
        (intake.part_sources, "part_sources"),
        (intake.feature_sources, "feature_sources"),
    ):
        for key, sources in mapping.items():
            missing = [s for s in sources if s not in source_ids]
            if missing:
                unknown_sources[f"{name}.{key}"] = missing

    assumption_ids = {a.id for a in intake.assumptions}
    question_ids = {q.id for q in intake.open_questions}
    requirement_ids = {r.id for r in intake.requirements}
    non_req = assumption_ids | question_ids

    def _assumption_only(sources: list[str]) -> bool:
        return (
            bool(sources)
            and not any(s in requirement_ids for s in sources)
            and any(s in non_req for s in sources)
        )

    assumption_only_parts = [
        p for p in part_ids if _assumption_only(intake.part_sources.get(p, []))
    ]
    assumption_only_features = [
        f for f in feature_ids if _assumption_only(intake.feature_sources.get(f, []))
    ]

    reasons: list[str] = []
    if not sha_matches:
        reasons.append("intake brief_sha256 does not match the brief")
    if unmapped_parts:
        reasons.append(f"unmapped parts: {','.join(unmapped_parts)}")
    if unmapped_features:
        reasons.append(f"unmapped features: {','.join(unmapped_features)}")
    if unknown_parts:
        reasons.append(f"unknown part ids: {','.join(unknown_parts)}")
    if unknown_features:
        reasons.append(f"unknown feature ids: {','.join(unknown_features)}")
    if unknown_sources:
        reasons.append("unknown source ids in mappings")
    if intake.open_questions:
        reasons.append(f"open questions: {len(intake.open_questions)}")
    evidence_errors = check_evidence(intake, intake_path=intake_path)
    reasons.extend(evidence_errors)

    return IntakeReport(
        brief_path=brief_path,
        intake_path=intake_path,
        brief_sha256=expected,
        intake_sha256=intake_sha256(intake),
        sha_matches=sha_matches,
        unmapped_parts=unmapped_parts,
        unmapped_features=unmapped_features,
        unknown_parts=unknown_parts,
        unknown_features=unknown_features,
        unknown_sources=unknown_sources,
        assumption_only_parts=assumption_only_parts,
        assumption_only_features=assumption_only_features,
        open_questions=intake.open_questions,
        evidence_errors=evidence_errors,
        verdict="blocked" if reasons else "ready",
        reasons=reasons,
    )


def check_evidence(intake: Intake, *, intake_path: Path) -> list[str]:
    """Verify every declared evidence file exists and matches its sha256."""
    errors: list[str] = []
    base = intake_path.resolve().parent
    for record in [*intake.assumptions, *intake.open_questions]:
        evidence = record.evidence
        if evidence is None:
            continue
        path = evidence.path if evidence.path.is_absolute() else base / evidence.path
        label = f"{record.id} evidence {evidence.path}"
        try:
            data = path.read_bytes()
        except OSError:
            errors.append(f"{label}: file missing")
            continue
        if hashlib.sha256(data).hexdigest() != evidence.sha256:
            errors.append(f"{label}: sha256 mismatch")
    return errors
