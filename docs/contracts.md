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
position_mm?}`). `position_mm` is measured from the **minimum corner of
the generated assembly's axis-aligned bounding box** (x = width, y =
depth, z up) — the same lower-left convention the DXF hole tables use.
The `harness_anchor.within_envelope` gate check (`{id, subject,
status, measured, limit, detail}` shape) passes when every coordinate
lies within [-1, size+1] mm of the assembly bbox in that frame; anchors
without `position_mm` produce no check.

`drawing` (`DrawingInfo`, all optional) carries the ISO 7200 title-block
data a brief cannot derive: `legal_owner`, `identification_prefix`
(drawing number is `<prefix or name>-<part_id>`), `revision` (default
`A`), `responsible_dept`, `technical_reference`, `created_by`,
`approved_by`, `date_of_issue` (ISO date; requires `approved_by`),
`supplementary_title`, `classification`, `language` (default `en`). The
document status is derived, never declared: `Released` (approver and issue
date), `In approval` (approver only), otherwise `In preparation`. Unset
fields print `—` on the sheet. Producer branding is never drawn; the
`GENERATOR` row names the tool (ADR-0008).

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
  summary, parts, references, provenance}` (`src/mech/gates.py::GateReport`,
  `report.py`). When author renders ran: `renders: {status: "ok", files:
  [{kind: dxf|views, source, png_path, image_sha256}]}` (or `{status:
  "error", detail}`); the markdown gets an advisory "Renders (advisory —
  review each)" section. Render entries are L2 advisory — they never
  change `verdict`.
- `*.advisory.json` — `src/mech/advisory.py::AdvisoryResult` `{tool,
  stage, status, summary, artifacts, detail}`; `vision_review` detail =
  `VisualReviewDetail` `{image_path, image_sha256, model, checklist,
  impression (≥400 chars, ≥3 sentences), findings[] {category, severity,
  note, bbox?}}`.

## Sister contracts

- `*.board-geometry.json` (consumed) — circuit-agent `circuit_board_geometry`
  v1, mirrored strictly in `src/mech/board_geometry.py`. Pin it with
  `enclosure.board.source {path, sha256}` (path relative to the brief, or
  to the workspace for MCP). The `board_geometry` gate checks, in the shared
  board-centred frame (front = -y): file hash = pin (else `fail`), circuit
  verdict `pass` (else `unknown`), width/depth/thickness within 0.05 mm,
  `keepout_height_mm` ≥ tallest top-side part, a 1:1 mount-hole match
  within 0.05 mm, and for every edge connector an opening on that face
  spanning its courtyard (less the 0.25 mm IPC excess) and overlapping its
  z range above (top) or below (bottom) the board.

- `enclosure.ruggedness` (`RuggednessSpec`, authored) — `board_material`
  (`youngs_mpa`, `poisson`, `density_kg_m3`, `component_mass_g`; required
  with `vibration`), `vibration` (`psd_g2_hz`, `q?`, `min_fn_hz?`,
  `parts[]` of `ref`/`x_mm`/`y_mm` (board-local)/`length_mm`/`parallel_to`/
  `steinberg_c`, refs unique), `drop` (`height_mm`, `pulse_ms`,
  `restitution` 0–1, `max_shock_g`), `ip_code` (`IP[0-6X][0-9X]`) and
  `sealed`; at least one of vibration, drop, ip_code. `response_path?`
  points at simulation's `*.sim-response.json` (relative to the brief, or to
  the workspace for MCP); it is not part of the simulation brief, so moving
  it does not change the request.
- `appearance` (optional, any design type) — `viewing` (`distance_mm`,
  `illuminance_lux`, `time_s`, `angle_deg` 0–90, `source` required),
  `surfaces[]` (`face` from the design type's faces: enclosure
  front/back/left/right/top/bottom, bracket base/leg/plate, spur_gear
  face/hub/bore/teeth; `cosmetic_class` A/B/C; `defects[]` of `defect`,
  `max_count`, and `max_size_mm` — or `max_delta` for `color_deviation` /
  `gloss_deviation`), and `samples[]` (`LS<n>`, `face`, `defect`, `side`
  accept/reject, `description`). Faces, defects per face and sample ids are
  unique; molding-only (`sink_mark`, `flow_line`, `weld_line`,
  `gate_vestige`, `ejector_mark`, `flash`), fdm-only (`layer_line`) and
  machining/sheet-metal-only (`burr`) defects are rejected for other
  processes; class A/B faces need defect limits, and each of their limits
  exactly one accept and one reject sample.
- `*.mech-appearance.json` (produced) — `mech_appearance` v1 projection of
  `appearance` for production-engineering (faces and defects sorted, samples
  in id order, `brief_sha256`).
>>>>>>> origin/main
- `*.ruggedness.sim.json` / `*.ruggedness.sim-request.json` (produced) —
  simulation-agent brief v1 with a `ruggedness` section (plate size and
  thickness from `enclosure.board`; `openings_min_mm` = the smaller side of
  each rect opening, the diameter of each round one, and the vent slot
  width) and a v1 `SimulationRequest` (`from_system: mech`,
  `kind: ruggedness`, `request_id` = `<name>-ruggedness-<brief sha256[:12]>`).
  Mech does not judge ruggedness; simulation's gates do.
- `*.ruggedness.sim-response.json` (consumed) — simulation-agent
  `SimulationResponse` v2, mirrored strictly in `src/mech/sim_response.py`.
  The `sim_ruggedness` gate checks, in order (first miss wins): response set
  and present, valid (`accepted` ⇔ pass, `rejected` ⇔ fail, hashed report),
  the sibling `*.sim-request.json` still hashes to `request_sha256` and is a
  `mech`/`ruggedness` request, `request_id` and `brief_sha256` equal what the
  *current* brief would request (else stale → `fail`), status not
  `needs_info`/`deferred` (else `unknown`), and the report under the
  workspace still hashes to `sha256` with a verdict equal to the response.
  It then reports each simulation `ruggedness.*` check as
  `sim_ruggedness:<check>` with simulation's verdict, measured value and
  limit — a simulation `fail`/`unknown` is never promoted. Without
  `enclosure.ruggedness` the gate emits nothing.

- `*.envelope.json` — wire-agent `EnvelopeSource`: `{schema_version: 1,
  system: "mech", anchors: [{name, kind, position_mm?}]}` (unchanged —
  wire validates strict).
- `*.envelope.provenance.json` — `{schema_version: 1, system: "mech",
  envelope_sha256, brief_path?, brief_sha256?, design_report_sha256?,
  decision_refs?, anchor_frame: "assembly-bbox-min-corner"?,
  step_frame_offset_mm: [x,y,z]?}` — the frame fields are present when
  the assembly STEP (`<brief name>.step` beside the envelope, written by
  author/export) could be read: `step_frame_offset_mm` is the assembly
  bbox minimum in STEP coordinates, so STEP point = anchor
  `position_mm` + offset. The `mech_render_views`/`render-views
  --envelope` overlay requires them and fails closed without them.

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
