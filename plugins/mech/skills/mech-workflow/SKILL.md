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
