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

## Findings / not done (and why)

- **Envelope anchors do not share the assembly STEP frame.** Hypothesis
  test: example anchors `(60,0,20)` and `(40,55,10)` lie outside the
  assembly bbox `(-40..40, -30..30, 0..30)` — they fit a corner-origin
  reading `(0..80, 0..60, 0..30)` instead. The anchor overlay in
  `render_views` was dropped per the brief; tracked in
  `tests/test_render.py::test_envelope_anchors_not_in_step_frame`.
  Follow-up: decide whether `position_mm` is corner-origin design-frame
  (worth documenting in `brief.py`) and only then consider re-adding an
  overlay with the translation derived from the part frame.
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
