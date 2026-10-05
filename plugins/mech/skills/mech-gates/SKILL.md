---
name: mech-gates
description: Deterministic gate checks for generated mechanical designs — what each verifies and how to fix failures.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - gates
  - verification
  - design review
  - 検証
---

# Deterministic gates

`mech_author` / `mech_gates` regenerate the design and run every check, writing
`design-report.json` with `verdict: pass|fail`. Missing tools, parse failures,
unexecuted checks, and `unknown` statuses are all fail-closed.

## Check inventory

| id                  | verifies                                                        |
|---------------------|-----------------------------------------------------------------|
| kernel_valid        | generated solids pass OCCT validity (`is_valid`)                |
| reload_valid        | written STEP re-imports valid with matching volume              |
| mesh_consistency    | STL facet count, volume (±5%), bbox (±0.6 mm) vs STEP          |
| interference        | pairwise part ∩ part volume < 0.01 mm³; parts ∩ board keepout   |
| board_envelope      | board keepout stays inside the cavity envelope                  |
| openings_clear      | each opening removes ≥50% of its nominal volume through the band|
| wall_thickness      | min distance between dominant opposing faces (≥5% area filter)  |
| dfm.*               | process limits: wall, hole, feature, draft, rib ratio, edge dist|
| mechanism.*         | snap strain, rib/boss dims, gear teeth/backlash, hinge, detent  |
| fits                | ISO 286 clearance window matches the declared intent            |
| stackup             | worst-case/RSS window inside the declared min..max              |
| manifest            | every artifact sha256 in `manifest.json` matches the file       |

## Fixing failures — always fix the brief, never the artifact

- `interference` — move openings/features off the keepout or bosses; reduce a boss OD.
- `openings_clear` — the opening was blocked (boss/rib in its path) or placed outside
  the face span; move it or shrink it.
- `wall_thickness` — raise `wall_mm`/`floor_mm`; the measurement already excludes
  sub-5% feature faces but includes real walls like the snap skirt.
- `dfm.*` — increase the offending dimension or change `process`/`material`.
- `stackup` — widen the declared `min..max` or reduce element tolerances; never trim
  declared element tolerances to squeeze in.
- `mesh_consistency` / `reload_valid` — kernel export defects; simplify the feature
  that produced the bad boolean and re-run.

`unknown` means the check could not run (missing artifact, tool error) — resolve the
cause; do not treat it as pass.

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
