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
