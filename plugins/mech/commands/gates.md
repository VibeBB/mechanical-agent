---
description: Re-run all deterministic gates for an existing mechanical design.
argument-hint: <brief.json> <out_dir>
allowed-tools:
  - terminal
---

Run `python3 -m mech.cli gates --brief <brief.json> --out <out_dir>` and report the JSON
verdict verbatim. The gates re-generate the design and re-check kernel validity, STEP
round-trip, STL consistency, interference, board keepout, opening penetration, wall
thickness, DFM/mechanism/fit/stackup rules, and manifest hashes. A `fail` or
`unknown` check means the design is not done — fix the brief and re-run
`mech_author` (`python -m mech.cli author`) rather than editing artifacts.
