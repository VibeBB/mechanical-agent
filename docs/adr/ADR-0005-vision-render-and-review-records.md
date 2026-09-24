# ADR-0005 Vision render pipeline and typed review records

- Status: Accepted
- Date: 2026-09-24
- Ports: electrical-circuit-agent ADR-0013/ADR-0019 (rasterizer env
  override) and ADR-0018 (typed visual review records)

## Context

ADR-0003 fixed vision as an L2 advisory lane: intake images are
provenance-bound (ADR-0004) and review may look at renders, but nothing
visual is ever promoted to a verdict. Until now mech had no renderer of
its own — the review lane depended on orchestrator-produced screenshots,
and the `record-image-observation` hook already matched `mech_render`, a
tool that did not exist. The DXF export was machine-checkable
(`mech_dxf_lint`) but invisible to vision models.

## Decision

`src/mech/render.py` rasterizes an exported `.dxf` deterministically:
the modelspace is drawn to SVG in-process via `ezdxf.addons.drawing.svg`
(no new Python dependency), then converted to PNG with `rsvg-convert`
(`librsvg2-bin` in the tools image; override via `$MECH_RSVG_CONVERT`,
same pattern as circuit's `$CIRCUIT_RSVG_CONVERT`). A missing or failing
rasterizer raises `RenderError` — a typed tool error, not a silent skip —
while a missing or empty DXF also fails closed.

`python -m mech render` and the `mech_render` MCP tool expose the same
function. The MCP result carries the JSON payload as text **plus** the
PNG as `types.ImageContent`, so a vision-capable model sees the drawing
inline — identical to circuit's `circuit_render` pattern. The render is
idempotent: same DXF, same pixels.

`render_dxf(..., baseline_path=...)` gives the vision lane a deterministic
change detector without any image diffing: a missing baseline JSON
records `{image, image_sha256, recorded_at}`; an existing one reports
`baseline: "match"|"diff"` plus `baseline_sha256`, so review can ask
"did the drawing change?" as a closed question instead of asking the
model to eyeball pixel drift.

`src/mech/advisory.py` ports circuit's typed review contract:
`VisualReviewDetail`/`VisualFinding`/`AdvisoryResult` plus
`parse_visual_review`, which returns `None` on any validation failure so
a malformed model answer can never masquerade as a record. Records are
written as `review-visual-<slug>.advisory.json` next to
`design-report.json` with mech-scoped checklists
(`dxf_outline`/`part_render`/`intake_image`) and finding categories.

Renders (`.svg`, `.png`) are projections of the brief like every other
artifact, so `protect-generated` now guards those suffixes too.

## Consequences

- The `mech_render` name in the `record-image-observation` matcher and
  the plugin docs is now backed by a real tool; rendered PNG paths flow
  into `image-observations.jsonl` automatically via the text payload.
- `scripts/e2e_authoring.py` renders every exported DXF fail-open and
  reports `renders`/`render_status` in the e2e payload; `skipped: ...`
  documents environments without `rsvg-convert`.
- `mech doctor` stays binary pass/fail and does not probe the
  rasterizer: a missing `rsvg-convert` would fail hosts where the
  advisory lane is legitimately unavailable.
- Everything in this ADR remains L2: nothing here can produce a
  pass/fail verdict; only `gates.py` can.
