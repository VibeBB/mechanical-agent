# Agents

Four task sub-agents in `plugins/mech/agents/`, invoked only via the SDK
`task` tool (`TaskToolSet`). Each declares its required hooks because
plugin hooks do not propagate to sub-agents.

## mech-brief

Requirement/intake conversation. Writes `<name>.brief.json` +
`<name>.intake.json`; resolves `Q*` open questions with the orchestrator;
runs `mech_validate_brief` then `mech_intake` until `ready`. Reads
user-attached images via `inspect_image_with_vision` (or the model's own
vision); adopted details become `A*`/`Q*` with image evidence binding —
never `R*`. Checks the UX liaison inbox at session start and answers
every request targeting mech. Leaves intake decisions, `intake_image`
vision reviews, and a stage impression.

## mech-design

Runs `mech_author` (or `mech_launcher.py author --brief <f> --out out/<n>`):
generation → export → gates → report. Fixes failing checks in the brief,
never in artifacts; treats `unknown` as failure. After `verdict: pass`,
renders the assembly views sheet (`mech_render_views`) and records an
`assembly_render` vision review self-check before handoff. Records a
decision per non-trivial choice and the author stage impression.

## mech-review

L2 advisory pass. Renders every `.dxf` and every `.step`, inspects each
image, and files `review-visual-<slug>.advisory.json` via the
`review-record` CLI (advisory only; the VRP v2 `vision_review` is recorded
separately with `mech_record_vision_review`) —
baseline fidelity, manufacturing completeness, design intent. Also checks
declared dimensions against the report's measured values and sanity-checks
fits/stackups/mechanism features. Never promotes findings to a verdict.

## mech-blind-review

Independent second vision review of one `*.views.png` views sheet or
`*.section-*.png` cross-section (`reviewer: "blind"` in round 1,
`"tiebreak"` in round 2). The `blind-guard` hook denies reads of
`observations/`, advisories, liaison answers and bard songs, so the first
review cannot anchor it. It writes two or more exact-token claims with
lookback checks through `mech_record_vision_review`, replies with the event
id only, and has no verdict authority; the caller reconciles, and a split
after the tiebreak stays `unknown`. It declares no `task_tracker`.
