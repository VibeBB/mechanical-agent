---
name: mech-workflow
description: Execute a conversational mechanical design workflow with deterministic verification.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - mechanical design
  - mech workflow
  - 機械設計
  - 筐体設計
---

# Mechanical design workflow

Clarify requirements, identify the project directory, then orchestrate the three
sub-agents through the SDK task tools (`TaskToolSet` + `AgentDefinition` +
`TaskTrackerTool`; never DelegateTool or WorkflowToolSet).

1. `mech-brief` — writes `<name>.brief.json` + `<name>.intake.json`. Resolve every
   `Q*` open question with the user; the intake gate must report `ready`.
2. `mech-design` — runs `mech_author`: parametric generation → STEP/STL/3MF/DXF
   export → all deterministic gates → `design-report.json`. Failing checks are
   fixed in the BRIEF, never in the artifacts, until `verdict: pass`.
3. `mech-review` — L2 advisory pass over renders/DXF outlines and parametric
   consistency. Findings feed the brief, never a verdict.

## Domain coverage

- 筐体設計 (enclosure): shell+lid screw/snap, board keepout + standoffs, openings,
  vents — flagship v0.1.0 path.
- 構造設計 (bracket): plate/L/U with holes, inner fillet, gusset.
- 機構設計 (mechanism): involute spur gears + snap-fit/rib/boss modeled features;
  living-hinge and detent declarations are parametric-only.
- DFM: fdm/machining/molding/sheet_metal limits; ISO 286 fits; 1D stack-ups.

## Boundaries

- The brief and git are the source of truth; artifacts are projections and never
  flow back into inputs. The `protect-generated` hook blocks direct artifact edits.
- Gate JSON is the only pass/fail authority. LLM self-reports, conversation text,
  review findings, and vision-derived observations are never promoted to verdicts.
- Missing tools, unreadable artifacts, `unknown` checks → fail-closed.
- Text I/O always `encoding="utf-8"`. Never write secrets anywhere.

## Vision intake and review

- `mech-brief` may read user-attached images (sketches, photos, drawings) via
  `inspect_image_with_vision`; adopted details become `A*`/`Q*` with the image as
  source — never `R*`. The `intake-attachments` hook materializes attached
  images to `intake/attachments/<sha256[:12]>.<ext>` with a `manifest.jsonl`
  provenance record; an A* or Q* record can bind one of those files via its
  optional `evidence` field (`kind`, `path`, `sha256`, `note`) and
  `check_intake` verifies the bytes — fail-closed.
- `mech-review` inspects renders/projections with the model's own vision
  (`inspect_image_with_vision` covers only user-attached images, not workspace
  files); every vision call is
  hashed into `observations/mech/vision-tool-events.jsonl` by the post_tool_use hook.
  On `dxf_outline` drawings it reviews baseline fidelity, manufacturing
  completeness, and design intent per `plugins/mech/agents/mech-review.md`,
  and every `vision_review` record requires the `impression` field.

## Terminal tool notes

The terminal tool runs **one command per call**: a payload carrying several commands is bounced
as "Cannot execute multiple commands at once". Chain with `&&` inside a single command when you
need two steps, and write files with `file_editor` rather than multi-line heredocs.

## UX-creator liaison (SLP v2)

Check the liaison inbox at session start (`mech_ux_inbox`); answer every
request targeting mech via `mech_ux_respond` — `accepted`/`in_progress`
early, `done` only with passing gate verdicts plus decision/impression
refs. Envelopes for wire keep a `.envelope.provenance.json` sidecar
(envelope/brief/report sha256, decision refs).

## Records you must leave (VibeBB Record Protocol — mandatory, unprompted)

Record these without being asked; the Stop hook refuses to finish a
session that still owes them (see `docs/records-and-vision.md`).

- **Decision** (`mech_record_decision`) for every non-trivial choice —
  process, material, wall thickness, closure type, fits, tolerances,
  mount strategy: the question, the first principles / physical laws /
  standards it rests on, at least two options with pros and cons, the
  chosen option, a rationale of 200+ characters, evidence (artifact paths
  are hashed; cite datasheets or standards as references), assumptions,
  unknowns, residual risks and the observation that would reopen it.
  Reason from principles, not from habit.
- **Stage impression** (`mech_record_impression`) when a stage ends,
  after its final regeneration: 400+ characters and 3+ sentences on what
  you noticed, what works, what worries you, how a maker or user would
  read the result, and what to do next. List the stage's output files or
  directories so the impression is bound to their sha256.
- **Vision review** (`mech_record_vision_review`) every time you look at
  an image (a rendered drawing, a views sheet, a photo, a screenshot, an
  `inspect_image_with_vision` answer): findings plus a long-form
  impression of 400+ characters judging geometric accuracy, ambiguity,
  whether the design intent comes across, usefulness to the maker or
  user, and the next step — not only legibility. Bind it to `image_path`
  or to the vision event's `source_event_id`.

Vision and impressions are advisory: they never override a deterministic
gate verdict. Results do not have to be identical from run to run; the
reasoning must be recorded every run. `mech_records_status` shows what is
still owed.
