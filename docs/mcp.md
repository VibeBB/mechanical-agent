# MCP tools (`mech` stdio server)

`src/mech/mcp_server.py` exposes deterministic entry points only — the
same functions `python -m mech` uses. Every tool returns a JSON text
payload mirroring the CLI verdicts; failures become `isError` results
(`{ok: false, fail_closed: true, failure_reason}`), never crashes. Paths
are confined to `OPENHANDS_PROJECT_DIR` by `src/mech/workspace.py`;
symlink output paths are rejected.

Annotations: `readOnlyHint` for read tools, `destructiveHint` for write
tools; all are `idempotentHint: true`, `openWorldHint: false`.

## Environment / reference (read)

| Tool | R/W | Input | Output | Errors (`isError`) |
|---|---|---|---|---|
| `mech_doctor` | R | — | doctor verdict JSON: build123d/OCP/ezdxf/lib3mf/rsvg availability | never; each probe reports its own status |
| `mech_standards` | R | `kind: materials|processes|threads|bearings` | the corresponding standards table | unknown `kind` |
| `mech_validate_brief` | R | `brief: object` | `{name, design_type, part_ids, brief_sha256}` or validation issues | brief fails `DesignBrief` validation |
| `mech_intake` | R | `brief: object`, `intake: object` | `IntakeReport` JSON (R*/A*/Q* coverage, verdict ready\|blocked) | invalid brief/intake payload |
| `mech_fit_lookup` | R | `nominal_mm`, `hole_class`, `shaft_class`, `intent: clearance\|transition\|interference` | ISO 286 fit window + class verdict | never (unknown class → `unknown` verdict) |
| `mech_dxf_lint` | R | `drawing_path`, `output_path?` | advisory readability report (never a gate verdict) | unreadable/invalid DXF |

## Pipeline (write)

| Tool | R/W | Input | Output | Errors (`isError`) |
|---|---|---|---|---|
| `mech_author` | W | `brief`, `out_dir`, `render?: bool = true` | generate → export → gates → design-report; returns `GateReport.to_dict()` + `report_path` + `renders` (`{kind: dxf\|views, source, png_path, image_sha256}[]` or `{status: "error", detail}` — advisory only, never changes the verdict); the assembly `.views.png` is appended inline as ImageContent | invalid brief, generation/gate exception (fail-closed); a render failure is reported in `renders`, not `isError` |
| `mech_gates` | W | `brief`, `out_dir` | regenerate + gates against existing artifacts | invalid brief, generation/gate exception |
| `mech_export_envelope` | W | `brief`, `out_path` | writes `<name>.envelope.json` + `.envelope.provenance.json` (with `anchor_frame`/`step_frame_offset_mm` when the assembly STEP sits beside it); returns anchors + `envelope_sha256` | no harness_anchors, unreadable assembly STEP |
| `mech_board_import` | R | `geometry_path`, `source_path?` | same payload as `board-import` | missing/malformed geometry, circuit verdict `fail` |
| `mech_render` | W | `dxf_path`, `out_path?`, `dpi?`, `baseline_path?` | `.svg` + `.png` + `image_sha256` (+ baseline match/diff/recorded); PNG returned inline as ImageContent | missing/invalid DXF, missing rsvg-convert, corrupt baseline |
| `mech_render_views` | W | `step`, `envelope?`, `baseline_path?` | `<step>.views.svg` + `.views.png` third-angle 2x2 sheet ([top, iso] over [front, right], hidden edges dashed, anchor overlay when `envelope` given); PNG returned inline | missing/invalid STEP, missing rsvg-convert, envelope without `anchor_frame`/`step_frame_offset_mm` sidecar, corrupt baseline |

## Records — VRP (write, except status)

| Tool | R/W | Input | Output | Errors (`isError`) |
|---|---|---|---|---|
| `mech_record_decision` | W | `DecisionInput` schema | `{verdict, kind, path, record}` appended to `decisions.jsonl` | schema violation (rationale <200 chars, <2 options, chosen not in options, evidence path missing, …) |
| `mech_record_impression` | W | `StageImpressionInput` schema | record appended to `impressions.jsonl` | schema violation (impression not prose: <400 chars or <3 sentences), missing artifacts |
| `mech_record_vision_review` | W | `VisionReviewInput` schema | record appended to `vision-reviews.jsonl` | schema violation, neither `image_path` nor `source_event_id` bound |
| `mech_records_status` | R | — | counts per log + last Stop-hook verdict | never (malformed status file is reported in-payload) |

## Liaison — SLP v2

| Tool | Input | Output | R/W |
|---|---|---|---|
| `mech_ux_inbox` | — | `{requests: [{id, path, stage, risk, state, reasons, depends_on}], malformed: [{path, error}]}` | read |
| `mech_ux_respond` | `{request, status, reason?, artifacts?, gate_verdicts?, design_reports?, decision_refs?, impression_refs?, questions_for_user?}` | `{verdict, response, status}` — writes `liaison/<id>.ux-response.json` | write |

See [sister-cooperation.md](sister-cooperation.md) for the refusal rules
(`done` requires all-pass gate verdicts, ≥ 1 artifact, ≥ 1 decision_ref
and ≥ 1 impression_ref) and [records-and-vision.md](records-and-vision.md)
for the record schemas.
