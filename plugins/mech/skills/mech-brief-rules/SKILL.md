---
name: mech-brief-rules
description: Path rule — schema and provenance reminders injected whenever a *.brief.json or *.intake.json file is touched.
version: 0.1.0
license: BSD-3-Clause
paths:
  - "**/*.brief.json"
  - "**/*.intake.json"
---

# Mech brief file rules

- `*.brief.json` follows the `DesignBrief` schema in `src/mech/brief.py`
  (in plugin-only installs, see the canonical sample at
  `examples/enclosure.brief.json`). Keep part and feature ids stable —
  gates, generators, and intake bindings address them.
- Every claim in the matching `*.intake.json` must bind to a provenance
  source: `R*` user-stated requirement, `A*` assumption with rationale,
  `Q*` open question, `I*` imported source. Claims read off images are
  observations — A* or Q*, never R*.
- Generated projections (STEP/STL/3MF/DXF exports, manifest, provenance,
  design report) are never hand-edited — change the brief and re-export.
