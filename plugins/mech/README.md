# mech — OpenHands mechanical design plugin

Conversational mechanical design for OpenHands: a parent agent delegates to
`mech-brief` (intake), `mech-design` (authoring + gates), and `mech-review`
(advisory review) to turn natural-language requirements into verified CAD
artifacts (STEP/STL/3MF/DXF).

- `/mech:design` — full intake → author → review workflow
- `/mech:doctor` — CAD runtime diagnostics (build123d/OCP)
- `/mech:gates` — re-run all deterministic gates
- `/mech:export` — regenerate artifacts only

Skills: `mech-brief`, `mech-enclosure`, `mech-mechanism`, `mech-dfm`,
`mech-gates`, `mech-workflow`. Hooks: session-start doctor,
protect-generated (blocks direct artifact edits), stop report-design-status,
vision-event recorder. Deterministic core: `src/mech` (BSD-3-Clause).
