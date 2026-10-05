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

| Tool | Input | Output |
|---|---|---|
| `mech_doctor` | — | doctor verdict JSON: build123d/OCP/ezdxf/lib3mf/rsvg availability |
| `mech_standards` | `kind: materials|processes|threads|bearings` | the corresponding standards table |
| `mech_validate_brief` | `brief: object` | `{name, design_type, part_ids, brief_sha256}` or validation issues |
| `mech_intake` | `brief: object`, `intake: object` | `IntakeReport` JSON (R*/A*/Q* coverage, verdict ready|blocked) |
| `mech_fit_lookup` | `nominal_mm`, `hole_class`, `shaft_class`, `intent: clearance|transition|interference` | ISO 286 fit window + class verdict |
| `mech_dxf_lint` | `drawing_path`, `output_path?` | advisory readability report (never a gate verdict) |

## Pipeline (write)

| Tool | Input | Output |
|---|---|---|
| `mech_author` | `brief`, `out_dir` | generate → export → gates → design-report; returns `GateReport.to_dict()` + `report_path` |
| `mech_gates` | `brief`, `out_dir` | regenerate + gates against existing artifacts |
| `mech_export_envelope` | `brief`, `out_path` | writes `<name>.envelope.json` + `.envelope.provenance.json`; returns anchors + `envelope_sha256` |
| `mech_render` | `dxf_path`, `out_path?`, `dpi?`, `baseline_path?` | `.svg` + `.png` + `image_sha256` (+ baseline match/diff/recorded); PNG returned inline as ImageContent |
| `mech_render_views` | `step`, `baseline_path?` | `<step>.views.svg` + `.views.png` 2x2 sheet (front/top/right/isometric); PNG returned inline |

## Records — VRP (write, except status)

| Tool | Input | Output |
|---|---|---|
| `mech_record_decision` | `DecisionInput` schema | `{verdict, kind, path, record}` appended to `decisions.jsonl` |
| `mech_record_impression` | `StageImpressionInput` schema | record appended to `impressions.jsonl` |
| `mech_record_vision_review` | `VisionReviewInput` schema | record appended to `vision-reviews.jsonl` |
| `mech_records_status` | — | counts per log + last Stop-hook verdict |

## Liaison — SLP v2

| Tool | Input | Output | R/W |
|---|---|---|---|
| `mech_ux_inbox` | — | `{requests: [{id, path, stage, risk, state, reasons, depends_on}], malformed: [{path, error}]}` | read |
| `mech_ux_respond` | `{request, status, reason?, artifacts?, gate_verdicts?, design_reports?, decision_refs?, impression_refs?, questions_for_user?}` | `{verdict, response, status}` — writes `liaison/<id>.ux-response.json` | write |

See [sister-cooperation.md](sister-cooperation.md) for the refusal rules
(`done` requires all-pass gate verdicts, ≥ 1 artifact, ≥ 1 decision_ref
and ≥ 1 impression_ref) and [records-and-vision.md](records-and-vision.md)
for the record schemas.
