# Contracts

Every JSON contract this repo produces or consumes. Pydantic models are
the source of truth; all models are `extra="forbid"` unless noted.

## Inputs (agent-authored, truth source)

### `*.brief.json` — `src/mech/brief.py::DesignBrief`

`name`, `design_type` (enclosure|bracket|spur_gear), `material`,
`process` (fdm|machining|molding|sheet_metal), `description`; per-type
spec blocks: `enclosure` (`EnclosureSpec`: width/depth/height, wall/floor
thickness, corner radius, lid screw/snap, board keepout+standoffs,
openings, vents), `bracket` (`BracketSpec`: legs, thickness, holes,
gusset), `spur_gear` (`SpurGearSpec`: module, teeth, face width, bore,
helix); plus `fits[]`, `stackups[]`, `mechanism_features[]`,
`harness_anchors[]` (`{name, kind: clip|grommet|breakout|other,
position_mm?}`).

### `*.intake.json` — `src/mech/intake.py::Intake`

`requirements[]` (R* ids), `assumptions[]` (A*), `open_questions[]` (Q*),
each mappable to parts/features and optional `evidence` (`{kind, path,
sha256, note}` — image evidence is byte-verified by `check_intake`).

## Generated artifacts (projections, protected)

- `*.step/.stl/.3mf` — CAD exports (assembly + per part).
- `*.dxf` — dimensioned outlines; `*.dxf_lint.json` advisory readability.
- `*.views.svg` / `*.views.png` — 2x2 STEP views sheets (`views.py`).
- `*.svg` / `*.png` — DXF renders (`render.py`).
- `manifest.json` — sha256 of every exported file.
- `provenance.json` — license + `brief_sha256` + tool versions.
- `design-report.json` / `design-report.md` — `{schema_version: 1,
  verdict, checks: [{id, subject, status, measured, limit, detail}],
  summary}` (`src/mech/gates.py::GateReport`, `report.py`).
- `*.advisory.json` — `src/mech/advisory.py::AdvisoryResult` `{tool,
  stage, status, summary, artifacts, detail}`; `vision_review` detail =
  `VisualReviewDetail` `{image_path, image_sha256, model, checklist,
  impression (≥400 chars, ≥3 sentences), findings[] {category, severity,
  note, bbox?}}`.

## Sister contracts

- `*.envelope.json` — wire-agent `EnvelopeSource`: `{schema_version: 1,
  system: "mech", anchors: [{name, kind, position_mm?}]}` (unchanged —
  wire validates strict).
- `*.envelope.provenance.json` — `{schema_version: 1, system: "mech",
  envelope_sha256, brief_path, brief_sha256, design_report_sha256?,
  decision_refs?}`.

## VRP records — `src/mech/records.py`

Envelope on every line: `{schema_version: 1, kind, plugin: "mech",
sequence, event_id (sha256 identity), recorded_at}`.

- `decisions.jsonl` — `DecisionRecord` (see
  [records-and-vision.md](records-and-vision.md)).
- `impressions.jsonl` — `StageImpression` `{stage, artifacts: [{path,
  sha256}], impression}`.
- `vision-reviews.jsonl` — `VisionReview` `{image_path?, image_sha256?,
  source_event_id?, model, checklist, findings[], impression}`.
- `vision-tool-events.jsonl`, `image-observations.jsonl` — hook-written
  observation lines; `records-status.json` — last Stop verdict.

## SLP v2 — `src/mech/liaison.py`

`<id>.ux-request.json` (`UXRequestV2`) and `<id>.ux-response.json`
(`UXResponseV2`) — full field lists and states in
[sister-cooperation.md](sister-cooperation.md). Response fields:
`{schema_version: 2, system: "ux-creator", request, responder, status,
reason, input_hashes: {path: sha256}, artifacts: [{path, sha256}],
gate_verdicts: [{gate, verdict}], decision_refs, impression_refs,
questions_for_user, responded_at}`.
