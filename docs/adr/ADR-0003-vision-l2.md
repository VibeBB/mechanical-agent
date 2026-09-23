# ADR-0003: Vision as an L2 aid only

- Status: Accepted
- Date: 2026-09-23

## Context

OpenHands Software Agent SDK 1.49.4 supports vision-capable models
(`LLM.vision_is_active()` + `ImageContent`). Mechanical design is a
visual domain: users bring sketches, photos of existing hardware, and
datasheet drawings; and generated parts benefit from rendered-projection
inspection.

## Decision

Vision is adopted in exactly two L2 roles:

1. **Intake assistance** — `mech-brief` may read user-supplied images
   (sketches, photos, drawings) to propose `R*/A*/Q*` entries. The entries
   land in `intake.json` as text; the image itself is never a verdict
   input, and every image-derived claim must be recorded as an
   assumption `A*` or a requirement `R*` with the image named as source.
2. **Render review** — `mech-review` may render projections of generated
   parts and inspect them for anomalies (missing openings, obviously
   wrong proportions). Its observations are advisory text on top of the
   `design-report.json`; it has no pass/fail authority.

Hard rules:

- Vision observations are never promoted to gate verdicts. A part passes
  iff the deterministic gates pass — a blurry render or a misread sketch
  can only push toward stopping/rework.
- The `record-vision-tool-event` post_tool_use hook logs vision tool
  calls as L3 telemetry so image-derived intake claims stay auditable.
- Render-based measurement is prohibited: rendered pixels never replace a
  geometric measurement (all measurements come from the BRep kernel).

## Alternatives considered

- Render-and-measure pipelines (pixel-derived dimensions): rejected —
  duplicates the kernel with strictly worse accuracy and breaks
  determinism.
- No vision at all: rejected — intake sketches/photos are a real part of
  conversational mechanical design, and the L2 boundary already contains
  the risk.

## Consequences

- Model choice gates only convenience: with a non-vision model the
  workflow degrades to text intake + gate-only review; nothing else
  changes.
- Vision-derived assumptions can always be challenged via `Q*` open
  questions, which block `check_intake` until resolved.
