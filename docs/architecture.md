# Architecture

mech is an OpenHands plugin for conversational mechanical design. Two
layers exist and they never mix:

- **L1 — deterministic core** (`src/mech`): schemas, generators, gates,
  exporters. The only component allowed to produce pass/fail verdicts.
- **L2 — agent surface** (`plugins/mech`): skills, task sub-agents,
  commands, hooks, and the MCP server. Steers the work; cannot pass
  anything. Vision observations (rendered projections, user sketches) are
  L2 aids only (ADR-0003).
- **L3 — telemetry**: conversation events and hook logs. Observe only.

## Pipeline

```text
user conversation
  └─ mech-brief agent (L2) ──> intake.json   R* requirements, A* assumptions,
│                                            Q* open questions, mapped to
│                                            parts + features
  └─ mech-design agent (L2) ──> design.brief.json (validated by pydantic)
         │
         ▼  L1 only below this line
      generate(brief)   ── build123d parametric parts + reference solids
      export(brief)     ── STEP/STL/3MF/DXF + manifest.json + provenance.json
                          (DXF outlines are annotated: frame, extents dims,
                          hole diameters + tag, hole/openings/board-mount
                          tables, notes, ISO 7200 title block; each DXF also gets a
                          *.dxf_lint.json advisory readability report)
      run_gates(brief)  ── GateCheck[] -> GateReport (verdict pass|fail)
      write_report()    ── design-report.json + design-report.md
```

`python -m mech author` (or `mech_author` MCP tool, or
`scripts/e2e_authoring.py`) runs generate → export → gates → report in one
step. `python -m mech gates` re-runs the same gates against an existing
output directory (verify-only, no regeneration).

## Determinism contract

- Same brief → byte-identical STEP/STL artifacts: export pins the volatile
  STEP `FILE_NAME` timestamp and OCCT's NAUO ordinal. Two fields stay
  container-volatile by construction: lib3mf writes a fresh `p:UUID` per
  object (normalized in the model XML, but the zip64 container headers are
  not reproducible), and OCCT serializes DXF entity order and symmetric-
  hole sign conventions non-deterministically — the annotation pass adds
  entities derived from that outline, so its content varies the same way
  while ezdxf's own volatile fields (datetimes, version banner, GUIDs) are
  pinned. Determinism for those two
  is therefore asserted at content level (3MF zip entries, DXF entity
  tokens) in `test_export_deterministic`, not byte level. Every file is
  sha256-recorded in `manifest.json` and verified by the manifest gate.
- `provenance.json` pins `license` + `brief_sha256` + tool versions; the intake schema
  binds part/feature provenance to R*/A* ids, and `check_intake` refuses a
  brief whose hash no longer matches.
- Every gate check emits `{id, subject, status, measured, limit, detail}`.
  `unknown` (missing artifact, tool error, unmeasurable) fails the design —
  nothing is allowed to be silently skipped.

## Gate catalog

| Group | What it proves |
| --- | --- |
| kernel | OCCT `is_valid` + positive volume per part |
| reload | per-part STEP round-trips and volume-matches the in-memory solid |
| mesh | STL facet counts sane; 3mf loads and matches part count |
| interference | parts do not intersect (broadphase distance + boolean volume) |
| board envelope | board + keepout + clearance fit inside the cavity |
| harness anchors | declared `position_mm` inside the assembly bbox |
| openings | each declared opening actually pierces the wall (residual-material probe) |
| wall thickness | dominant-wall measurement ≥ process minimum |
| parametric | DFM rules (declared + measured), mechanism rules, fits vs intent, stackups |
| manifest | every artifact sha256 matches its manifest record |

## Generators

`src/mech/generators/` keyed by `brief.design_type`:

- `enclosure.py` — shell (walls + floor, snap skirt or screw ridge),
  lid (screw or snap), board keepout reference, standoffs, openings, vent
  grid. Mount features are welded 0.1–0.4 mm into the host to avoid
  tangent-union non-manifold meshes (see research notes).
- `bracket.py` — plate/L/U sections, inner fillet, optional gusset,
  declared hole faces.
- `gear.py` — involute spur gear with bore/hub.
- `features.py` — snap-fit cantilever, rib, boss attached to `mount`+`face`.

`living_hinge` and `detent` are parametric-only in v0.1.0 (rules run, no
geometry yet).

## Plugin surface

- **Skills** (7): brief/intake workflow, brief rules (path-triggered),
  enclosure recipe, mechanism recipe, DFM rule tables, gate
  interpretation, end-to-end workflow — see [skills.md](skills.md).
- **Agents** (3 task sub-agents): `mech-brief` (conversation → intake),
  `mech-design` (brief → author → views self-check), `mech-review`
  (reads design-report + renders projections; advisory only) — see
  [agents.md](agents.md).
- **Commands** (4): `/mech:design`, `/mech:doctor`, `/mech:gates`,
  `/mech:export` — see [commands.md](commands.md).
- **Hooks** (5 groups): `session_start` mech-doctor probe, intake
  attachments, LLM profiles, `require-records` session marker,
  `report-ux-inbox` pending liaison list; `pre_tool_use`
  `protect-generated` blocks writes to artifacts (stdin JSON, exit 2
  blocks) and `safety-rail` guards the terminal; `stop`
  `require-records` (first — refuses unfinished records) then
  `report-design-status`; `post_tool_use` vision event + image
  observation loggers — full inventory in [hooks.md](hooks.md).
- **MCP**: `.mcp.json` → `scripts/mech_launcher.py` (resolves plugin root,
  points PYTHONPATH at the matching `src/`) → `python -m mech.mcp_server`.
  Tools mirror CLI commands exactly — every tool documented in
  [mcp.md](mcp.md).

## Module reference (`src/mech`)

- `brief.py` — `DesignBrief` and all spec models (the contract source of
  truth); `load_brief`, `brief_sha256`.
- `intake.py` — `Intake`/`IntakeReport`, `check_intake`, `load_intake`
  (R*/A*/Q* coverage + evidence byte-binding).
- `standards.py` — materials, process limits, ISO metric threads,
  bearing seats; `material()`, `thread()`.
- `fits.py` — ISO 286 limits-and-fits (`evaluate_fit` → `FitResult`).
- `stackup.py` — 1-D worst-case + RSS stackups (`StackupResult`).
- `dfm.py` / `mechanism.py` — process rule checks and gear/snap/rib/
  boss/hinge/detent rules (`DfmFinding`, `MechanismFinding`).
- `generators/` — `generate(brief)` dispatch into parametric builders.
- `gates.py` — authoritative gate runner (`run_gates` → `GateReport`).
- `export.py` — `export_design`: STEP/STL/3MF/DXF + manifest + provenance.
- `dxf_annotate.py` — deterministic DXF frame/dims/title block overlay.
- `dxf_lint.py` — advisory readability lint (`lint_file`).
- `render.py` — `render_dxf` DXF→SVG→PNG + shared `rasterize_svg`,
  `sha256_file`, `record_or_compare_baseline`.
- `views.py` — `render_views` STEP→2x2 third-angle views sheet; `render_section` hatched cross-section
  (`ViewsResult`, optional anchor overlay via the envelope sidecar),
  `render_author_outputs` (author-time DXF + views renders).
- `advisory.py` — advisory envelope + typed visual-review records
  (`write_review_record`, `parse_visual_review`).
- `records.py` — VRP v1 typed writers (`record_decision`,
  `record_impression`, `record_vision_review`, `records_summary`,
  `tree_sha256`, `sha256_file`, `impression_is_prose`,
  `event_ids` — mech-local JSONL reader used by liaison/envelope).
- `liaison.py` — SLP v2 (`UXRequestV2`/`UXResponseV2`, `ux_inbox`,
  `ux_respond`, `liaison_dir`).
- `board_geometry.py` — strict mirror of circuit's board geometry,
  `resolve_source`, `suggest_board`; checks live in `gates.py`.
- `envelope.py` — `envelope_source`, `write_envelope` (envelope +
  provenance sidecar).
- `report.py` — `write_report` design-report.json/md.
- `doctor.py` — `run_doctor` environment probe.
- `mcp_server.py` — stdio MCP boundary (tool schemas, dispatch,
  annotations).
- `cli.py` — `python -m mech` subcommands.
- `workspace.py` — `workspace_root`, `workspace_path` (confinement),
  `reject_symlinks`.

## Error model

- Schema validation (`pydantic`) rejects malformed briefs/intakes before
  geometry work.
- `generate`/`export` raise → CLI wraps into `{verdict: fail, stage}`.
- Gate checks never throw past the report boundary; every measurement is
  wrapped, failures become `unknown`/`fail`.
- The MCP `call_tool` boundary catches all exceptions into
  `isError` CallToolResults.

## Where things extend

- New `design_type`: brief spec + generator + VALID_MOUNTS entry +
  docstrings/ADRs. The dispatch in `generators/__init__.py` fails closed on
  unknown types.
- New copyleft tool: subprocess adapter only, never an import (ADR-0001).
- New gate check family: append to `run_gates`; keep the `{id, subject,
  status, measured, limit, detail}` shape.
