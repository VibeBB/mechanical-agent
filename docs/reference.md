# Module reference (`src/mech`)

Public API surface of the deterministic core — generated from the code,
ordered by pipeline stage. Every function raises `ValueError`/
`RenderError`/`DxfLintError` (fail-closed) unless noted; paths passed to
MCP are confined to `OPENHANDS_PROJECT_DIR` (`workspace.py`).

## brief.py — the contract source of truth

- `class Opening` / `MountHole` / `BoardSpec` / `VentSpec` / `LidScrew` /
  `EnclosureSpec` — two-piece clamshell spec (board keepout, standoffs,
  openings, vents, lid fastening).
- `face_span(spec, face)` → `(width, height)` of a wall face in
  face-local coordinates.
- `standoff_diameters(hole_diameter_mm)` → `(outer, pilot)` diameters.
- `vent_slot_count(spec)` → number of vent slots (contract value).
- `class BracketHole` / `BracketSpec` — plate/L/U bracket spec.
- `class SpurGearSpec` — metric involute gear spec.
- `class MechanismFeature` — opt-in snap/rib/boss/hinge/detent feature.
- `class FitDeclaration` / `StackupElement` / `StackupChain` — ISO fit
  and 1-D tolerance chain declarations.
- `class HarnessAnchor` — wire-side fixturing point; `position_mm` is
  measured from the assembly bbox minimum corner (x=width, y=depth,
  z up — same lower-left convention as the DXF hole tables).
- `class DesignBrief` — top-level contract; validators: unique ids,
  material key, design_type block present, board inside the envelope.
- `brief_sha256(brief)` / `load_brief(path)` — canonical digest /
  strict load (raises `ValueError`).

## intake.py

- `class Requirement` / `Assumption` / `OpenQuestion` / `EvidenceRef` /
  `Intake` / `IntakeReport` — R*/A*/Q* schemas + byte-verified evidence.
- `load_intake`, `intake_sha256`, `check_intake(brief, intake, brief_path,
  intake_path)` → `IntakeReport` (fail-closed), `check_evidence(intake,
  *, intake_path)` → `list[str]` of violations.

## standards.py / fits.py / stackup.py

- `MaterialSpec`, `ProcessLimits`, `ThreadSpec`; `material(key)`,
  `process_limits(key)`, `thread(designation)` (raise `KeyError`).
- `hole_limits`, `shaft_limits` → `LimitsMm | None`;
  `evaluate_fit(nominal_mm, hole_class, shaft_class, intent)` → `FitResult`.
- `evaluate_chain(chain)` → `StackupResult` (worst-case + RSS).

## dfm.py / mechanism.py

- `check_dfm(brief, *, measured_min_wall_mm)` / `check_standoff_bosses(brief)`
  → `list[DfmFinding]`.
- `check_mechanism_features(brief)` / `check_gear_rules(brief)` →
  `list[MechanismFinding]`; `spur_gear_min_teeth(pressure_angle_deg)`.

## generators/ — parametric bodies (lazy build123d)

- `generate(brief)` → `GeneratedDesign` — dispatch; fail-closed on
  unknown `design_type` (living_hinge/detent are rules-only).
- `generate_enclosure`, `generate_bracket`, `generate_spur_gear`.
- `opening_prism(spec, opening, shell_height)` — the cutting solid a
  declared opening removes.
- `attach_snap_fit` / `attach_rib` / `attach_boss(feature, spec)` —
  feature builders on a `WallHost`.
- `common.build123d()` — lazy import; `GeneratedPart`, `ReferenceSolid`,
  `GeneratedDesign`, `BBox`, `shape_bbox(shape)`.

## gates.py — the only pass/fail authority

- `GateCheck{id, subject, status, measured, limit, detail}`,
  `GateReport{checks, verdict}.to_dict(brief)`.
- `run_gates(brief, design, out_dir, *, include_artifacts=True)` →
  `GateReport`. Check families: `kernel_valid`, `interference`,
  `board_envelope`, `harness_anchor.within_envelope`, `openings_clear`,
  `wall_thickness`, `dfm.*`, `mechanism.*`, `gear.*`, `fits`, `stackup`,
  `reload_valid`, `mesh_consistency`, `manifest`.

## export.py / report.py

- `export_design(brief, design, out_dir)` → manifest dict (STEP
  assembly + per part, STL, 3MF, DXF, provenance).
- `build_report(brief, design, gate_report)` → report dict;
  `write_report(..., out_dir, *, renders=None)` → design-report.json/.md
  path (renders land in an advisory `renders` section, never in
  `verdict`); `render_markdown(report)` → markdown string.

## render.py / views.py — vision-lane renders

- `render_dxf(dxf_path, out_path=None, *, dpi=200, baseline_path=None)`
  → `RenderResult`; raises `RenderError`.
- `rasterize_svg`, `sha256_file`, `record_or_compare_baseline` — shared
  helpers; `BaselineVerdict ∈ recorded|match|diff`.
- `render_views(step_path, *, envelope_path=None, baseline_path=None,
  dpi=200)` → `ViewsResult` — third-angle 2x2 sheet ([top, iso] over
  [front, right]); `envelope_path` overlays harness anchors and requires
  the provenance sidecar (`anchor_frame` + `step_frame_offset_mm`),
  else `RenderError`.
- `render_section(step_path, *, axis, offset_mm=0.0, baseline_path=None,
  dpi=200)` → `SectionResult` (`plane_mm`, `section_area_mm2`,
  `region_count`) — splits at the bbox centre + offset, projects the half
  behind the plane (front/right/top viewer for y/x/z), hatches cut faces;
  `RenderError` when the plane is outside the part or cuts no material.
- `render_author_outputs(name, part_ids, out_dir, *, dpi=200)` → list of
  `{kind, source, png_path, image_sha256}` — renders every DXF + a views
  sheet per STEP; raises `RenderError` on the first failure.

## board_geometry.py

- `BoardGeometry` — strict mirror of circuit's `circuit_board_geometry` v1.
- `load_geometry(path)`, `sha256_file(path)`,
  `resolve_source(brief, base_dir, *, confine=False)` → pinned path or `None`.
- `suggest_board(geometry, source_path, sha256)` → `{board, connector_openings}`;
  raises `ValueError` on an incomplete geometry.
- `along_span(component)` → face-local courtyard span less 0.25 mm.

## appearance.py

- `appearance_payload(brief)` → `mech_appearance` v1 payload; raises
  `ValueError` without `appearance`.
- `write_appearance(brief, out_dir)` → writes `<name>.mech-appearance.json`;
  returns `path`, `sha256`, `surfaces`, `samples`.

## sim_request.py

- `opening_min_dims(enclosure)` → IP probe size of every opening and vent slot.
- `ruggedness_brief(brief)` → simulation `*.sim.json` payload; raises
  `ValueError` without `enclosure.ruggedness` or, for vibration, a board.
- `write_sim_request(brief, out_dir, *, root=None)` → writes the brief and
  `*.sim-request.json`; `root` makes `brief_path` workspace-relative.

## advisory.py / records.py / liaison.py / envelope.py

- `build_review_record` / `write_review_record` → `review-visual-<slug>
  .advisory.json`; `parse_visual_review(result)` → `VisualReviewDetail`;
  `review_record_path(image_path, out_dir)`. Checklists: `dxf_outline`,
  `part_render`, `assembly_render`, `intake_image`.
- `record_decision` / `record_impression` / `record_vision_review`
  (typed VRP writers), `records_summary`, `records_dir`, `tree_sha256`,
  `impression_is_prose` (≥400 chars / ≥3 distinct sentences),
  `event_ids(log)` — mech-local helper reading event_ids from a VRP
  JSONL log (not in the wire original).
- `liaison_dir`, `ux_inbox(root)` → `{requests: [{id, path, stage, risk,
  state, reasons, depends_on}], malformed: [{path, error}]}` with states
  stale > answered > blocked > new; `ux_respond(payload, root)` → writes
  `liaison/<id>.ux-response.json` (refusals per ADR-0007). Strict
  mirrors `UXRequestV2` / `UXResponseV2` / `RespondPayload` /
  `RequestInput` / `GateVerdict`.
- `envelope_source(brief)` / `write_envelope(brief, out_path, *,
  brief_path, design_report_path, decision_refs)` → sidecar payload
  (adds `anchor_frame`/`step_frame_offset_mm` when the assembly STEP
  sits beside the envelope).

## dxf_annotate.py / dxf_lint.py / doctor.py / workspace.py

- `annotate_dxf(path, *, design, part_id, material, process, fits,
  enclosure)` — deterministic frame/dims/title-block overlay;
  `hole_circles(msp)`.
- `lint_file(path, output=None)` / `lint_text` → `DxfLintReport`
  (advisory, never a verdict; raises `DxfLintError`).
- `run_doctor()` — environment probe verdict.
- `workspace_root`, `workspace_path` (confinement, raises `ValueError`),
  `reject_symlinks`.

## cli.py / mcp_server.py

- `main(argv)` — `python -m mech` entry (`build_parser`); every
  subcommand prints a JSON verdict, fail-closed.
- `call_tool`, `handle_call_tool`, `tool_specs`, `list_tools`, `main` —
  the stdio MCP boundary mirroring the CLI one-to-one.
