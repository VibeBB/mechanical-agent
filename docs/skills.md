# Skills

`plugins/mech/skills/` — keyword skills use `triggers:` (model-invocable);
`mech-brief-rules` and `mech-out-rules` are path-triggered rules (`paths:`
glob, deterministic injection). The two mechanisms are exclusive.

| Skill | Kind | What it injects |
|---|---|---|
| `mech-workflow` | keyword (mechanical design / mech workflow / 機械設計 / 筐体設計) | the 3-agent conversational workflow, domain coverage, boundaries, vision lane, liaison inbox, mandatory records |
| `mech-brief` | keyword | brief/intake authoring guidance: R*/A*/Q* vocabulary, evidence binding |
| `mech-brief-rules` | `paths:` rule | brief schema rules injected whenever a matching file is edited |
| `mech-enclosure` | keyword | enclosure flagship path: shell+lid, keepout, standoffs, openings, vents |
| `mech-mechanism` | keyword | gear/snap/rib/boss/hinge/detent parametric rules |
| `mech-dfm` | keyword | process limit tables and DFM rule expectations |
| `mech-gates` | keyword | gate semantics, verdict handling, mandatory records section |
| `mech-out-rules` | `paths:` rule on `**/out/**` | generated artifacts under `out/` are read-only projections — change the brief and regenerate (the `protect-generated` hook enforces) |
