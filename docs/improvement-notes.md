# Improvement notes

Running list kept during the VibeBB refactor (2026-10). Each note:
problem, evidence, done / not-done and why.

## Done in this change

- **STEP views sheet fills the unused `part_render` checklist.** The
  advisory checklists declared `part_render` but nothing produced a part
  render. `src/mech/views.py` (`render_views` → `<step>.views.svg|.png`,
  `mech_render_views`, `render-views` CLI) now generates a 2x2
  front/top/right/isometric sheet; `assembly_render` was added to the
  checklist for the assembly sheet. Tests: `tests/test_render.py`.
- **Record protocol ported (VRP v1).** Shared hook pair copied
  byte-for-byte (hash-locked), `src/mech/records.py`, `mech_record_*`
  tools, `record` CLI, `require-records` hooks in `hooks.json`,
  `records-policy.json`, protect-generated covers the log names.
- **Advisory impression floor unified.** `advisory.py` now uses
  `records.impression_is_prose` (400 chars / 3 sentences), matching the
  VRP rule; `review-record` mirrors into `vision-reviews.jsonl`.
- **SLP v2 liaison.** `src/mech/liaison.py` (`UXRequestV2`/`UXResponseV2`
  strict mirrors), `mech_ux_inbox`/`mech_ux_respond`, `ux` CLI,
  `report_ux_inbox.py` session hook, `*.ux-response.json` write-protected.
- **Envelope provenance sidecar.** `export-envelope` also writes
  `<name>.envelope.provenance.json` (envelope/brief/report sha256 +
  optional decision refs); the envelope schema itself is unchanged so
  wire's strict `EnvelopeSource` still validates it.
- **Stale uv pin in CONTRIBUTING.md.** `uv ==0.12.22` → `==0.12.23`
  (`pyproject.toml [tool.uv] required-version`). Evidence:
  `CONTRIBUTING.md` line 10.
- **rsvg/baseline/hash helpers factored.** `render.py` now exposes
  `rasterize_svg`, `sha256_file`, `record_or_compare_baseline`, reused by
  `views.py` instead of duplicating.

- **Top view was mirrored** (`up=(0,-1,0)` → vent rendered on the
  wrong edge). Fixed to `up=(0,1,0)` and the sheet rearranged to true
  third-angle ([top, isometric] over [front, right]) with a footer
  naming the projection, file, and overall dims; each view is centered
  in its cell. Verified by `test_view_orientations`.
- **Anchor frame bug (cross-plugin).** Envelope `position_mm` values
  were undeclared-frame — they turned out to be design-frame
  (assembly-bbox min corner, like the DXF lower-left tables), not STEP
  coordinates. Now defined in `brief.py`, gated by
  `harness_anchor.within_envelope` (`[-1, size+1]` mm per axis), and the
  provenance sidecar carries `anchor_frame` +
  `step_frame_offset_mm` so the overlay draws them correctly
  (`test_envelope_anchors_land_in_assembly_bbox`).
- **Author-time renders** (`author --no-render` / `mech_author render:
  false` to skip): every DXF + a views sheet per STEP is produced after
  gates, listed in `design-report` under `renders`, and the assembly
  sheet is returned inline by the MCP tool. L2 only — a render error is
  reported, never a verdict change. `mech_author` added to the
  image-observation matcher.
- **Liaison correctness vs the UX producer** (`requests.py`):
  `created_at`/`responded_at` must be tz-aware ISO-8601, list items must
  be non-empty, high-risk needs a 20+ char rationale containing a
  job-id-shaped token (membership stays UX-side), inbox entries carry
  `reasons` (input changed/missing, response hash drift, unanswered
  deps, cycle path, malformed response).
- **Author renders coexistence**: verified `gates` on an authored+rendered
  dir still passes — renders are not manifest entries
  (`test_cli_author_renders_and_gates_rerun`).

## Findings / not done (and why)

- **README sister list.** Old README listed only 4 of 11 sisters; the new
  README names all eleven (UX-creator, bard, dashboard, document,
  electrical-circuit, firmware, fpga, mechanical,
  production-engineering, simulation, wire) and https://vibebb.org/.
- **docker/README.md** states Python 3.12 via `uv python install`,
  consistent with `requires-python >=3.12` and the CI matrix floor — no
  fix needed.
- **CI/publish workflow changes** — none required for this refactor;
  anything touching `.github/workflows` would need the family-wide
  `check_shared_workflows.py` updated in all 11 copies together and is
  intentionally left out.
- **`mech_records_status` / stop-hook denials count per session** —
  `records-status.json` keeps only the last verdict; a rolling history
  could help debugging but would add a non-canonical file name the
  shared hook does not write. Left as-is (shared files are byte-locked).
- **`living_hinge` and `detent` have rules but no geometry** —
  `generators/__init__.py` dispatches only enclosure/bracket/spur_gear
  bodies; mechanism features snap/rib/boss attach, hinge/detent are
  parametric-only (see architecture.md). Needs a generator + DXF/export
  path before they're designable.
- **No FEA / physics validation anywhere** — gates are geometric and
  rule-table only (kernel validity, reload, mesh, interference, wall
  thickness, DFM/fits/stackups, anchors). Thermal, drop, fatigue,
  fastener-torque, and mold-flow are out of scope by design; simulation
  results would arrive via the simulation sister's artifacts.
- **Single-board enclosures** — `EnclosureSpec.board` is singular; no
  daughterboard/flex/connector-frame modeling. Multi-board needs a
  spec change and an interference path for board-board clearance.
- **`depends_on` only inspects the liaison dir** — requests pinned to
  files outside the workspace are reported `input outside workspace`
  (stale), which is correct fail-closed behavior but means UX must
  stage inputs inside the workspace.
- **Anchor tolerance is fixed at ±1 mm** in
  `harness_anchor.within_envelope`; a per-process anchor tolerance would
  need a brief field.
- **High-risk job-id validation is shape-only on this side** — mech
  checks for a 20+ char rationale containing a job-id token; real
  membership vs the UX contract is UX-creator's check (documented in
  `liaison.py`).
- **`project_to_viewport` self-occlusion quality** — the hidden-line
  split is OCCT's; dense geometry (vent grids) produces many short
  dashed polylines. Fine for review, not a drawing-quality HLR package.
