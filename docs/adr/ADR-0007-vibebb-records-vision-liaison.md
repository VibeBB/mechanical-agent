# ADR-0007: VibeBB records, STEP views vision point, sister liaison

Status: accepted (2026-10-05)

## Context

The VibeBB family adopted the Record Protocol (VRP v1, canonical in
wire-agent), a family-wide Sister Liaison Protocol (SLP v2) directed by
UX-creator, and "vision everywhere" at artifact/stage/decision points.
mech needed the same machinery plus a STEP-level render so the
`part_render`/`assembly_render` checklists have something to look at.

## Decision

- Port VRP v1 exactly: `_records.py`/`require_records.py` copied
  byte-for-byte (normalized-AST hash-locked in
  `scripts/check_shared_hooks.py`), `src/mech/records.py` typed writers,
  `mech_record_*` MCP tools + `record` CLI, `require-records` registered
  session-start and first-in-stop, `records-policy.json` with mech
  artifact globs. The advisory impression floor moves from 240/2 to the
  VRP rule (400 chars / 3 distinct sentences) and `review-record` mirrors
  into `vision-reviews.jsonl`.
- Add `render_views`: `project_to_viewport` (build123d 0.13) into a 2x2
  front/top/right/isometric SVG sheet — visible edges solid, hidden thin
  dashed, labels + bbox dimensions — rasterized through the same
  rsvg-convert path as `render_dxf` (shared helpers factored out of
  `render.py`). Missing rasterizer or projection error → `RenderError`
  (fail-closed). The MCP tool returns the PNG inline.
- **No envelope anchor overlay.** The planned overlay assumed anchors
  share the assembly STEP frame; the example's anchors prove they do not
  (they fit a corner-origin design frame instead). The overlay was cut
  and the frame question recorded in `docs/improvement-notes.md`.
- SLP v2 via local strict mirrors (`UXRequestV2`/`UXResponseV2`,
  `extra="forbid"`, no UX imports): `mech_ux_inbox` (new/answered/
  stale/blocked + malformed), `mech_ux_respond` (writes
  `liaison/<id>.ux-response.json`, `done` requires all-pass gates +
  artifacts + decision/impression refs), `report_ux_inbox.py`
  session-start hook, and `*.ux-response.json` under `protect-generated`.
- Envelope stays byte-compatible for wire's strict schema; provenance
  moves to `<name>.envelope.provenance.json`.

## Consequences

Sessions that produce artifacts or look at images must leave records or
the Stop hook denies finishing (bounded by `max_stop_denials: 2`). All
new writes are deterministic, workspace-confined, and covered by tests
(`test_records.py`, `test_liaison.py`, `test_render.py`,
`test_envelope.py`).
