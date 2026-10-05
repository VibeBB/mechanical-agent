# Workflow

The conversational design workflow (skill `mech-workflow`, command
`/mech:design`) orchestrates the three sub-agents through the SDK task
tools (`TaskToolSet` + `AgentDefinition` + `TaskTrackerTool`).

## Stages

1. **intake / brief** — `mech-brief` clarifies requirements and writes
   `<name>.brief.json` + `<name>.intake.json`. Every `Q*` open question
   is resolved with the user; `mech_intake` must report `ready` before
   design starts. Attached images become `A*`/`Q*` evidence (never `R*`).
   Records: decisions for resolved trade-offs, `intake_image` vision
   reviews, stage impression bound to the intake/brief files.
2. **author** — `mech-design` runs `mech_author` (parametric generation →
   STEP/STL/3MF/DXF → all deterministic gates → `design-report.json`).
   Failing checks are fixed in the BRIEF, never in the artifacts, until
   `verdict: pass`. After a pass it renders `mech_render_views` on the
   assembly STEP and records an `assembly_render` vision review as a
   design-intent self-check before handing off.
   Records: one decision per non-trivial choice (process, material, wall
   thickness, closure type, fits, tolerances, mount strategy), stage
   impression bound to the out dir.
3. **review** — `mech-review` renders every `*.dxf` (`mech_render`) and
   every `*.step` (`mech_render_views`), looks at each PNG, and files a
   `vision_review` (`dxf_outline` / `part_render` / `assembly_render`)
   plus a parametric sanity pass over `fits[]`/`stackups[]`/mechanism
   features. Findings feed the brief; never a verdict.

## Boundaries

- The brief and git are the source of truth; artifacts are projections —
  the `protect-generated` pre_tool_use hook blocks direct edits.
- Gate JSON is the only pass/fail authority; LLM self-reports, review
  findings, and vision observations are L2 aids and can only push toward
  stopping, never passing.
- Missing tools, unreadable artifacts, `unknown` checks → fail-closed.

## Liaison

At session start the `report-ux-inbox` hook lists pending
`liaison/*.ux-request.json` for mech; `mech_ux_inbox` gives full state and
`mech_ux_respond` answers each (see
[sister-cooperation.md](sister-cooperation.md)).

## Records left

See [records-and-vision.md](records-and-vision.md): a decision for every
non-trivial choice, a stage impression at the end of every stage bound to
that stage's artifacts, and a vision review for every image looked at.
The Stop hook refuses to finish a session that still owes them.
