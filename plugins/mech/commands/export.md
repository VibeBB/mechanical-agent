---
description: Export CAD artifacts (STEP/STL/3MF/DXF) for an existing design brief.
argument-hint: <brief.json> <out_dir>
allowed-tools:
  - terminal
---

Run `python3 -m mech.cli export --brief <brief.json> --out <out_dir>` to regenerate the
parts and write the assembly STEP, per-part STEP/STL/DXF, the combined 3MF,
`manifest.json` (per-file sha256), and `provenance.json`. Export does not run gates —
use `/mech:gates` or `mech_author` when a verdict is needed. Never write artifacts to
paths the protect-generated hook protects by hand-editing; always export.
