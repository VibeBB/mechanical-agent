---
description: Orchestrate a conversational mechanical design workflow (enclosure, bracket, or gear).
argument-hint: <project_dir> <requirements summary>
allowed-tools:
  - task_tracker
  - task_tool_set
  - terminal
---

Clarify requirements with the user, create a task-tracker plan, then delegate first to
`mech-brief`. Resolve every returned `open_questions` item with the user and repeat
until the intake verdict is `ready`. Only then delegate to `mech-design` and
`mech-review` through the SDK task tool set. The JSON gate verdicts, not a sub-agent
opinion, determine pass or fail.

Use `TaskToolSet`, `AgentDefinition`, and `TaskTrackerTool`; do not use the deprecated
DelegateTool or WorkflowToolSet.

For a new design, first delegate conversation intake to `mech-brief`, which writes a
machine-readable `*.brief.json` plus intake sidecar. The brief chooses one of three
design types: `enclosure` (shell+lid, board keepout, standoffs, openings, vents),
`bracket` (plate/L/U with holes and optional gusset), or `spur_gear` (involute teeth,
bore, hub). It may also carry `mechanism_features` (snap fits, ribs, bosses, living
hinges, detents), `fits` (ISO 286), and `stackups` (1D tolerance chains). A blocked
intake must stop delegation — never hand an unready brief to `mech-design`.

Then delegate to `mech-design`: it runs `mech_author` (generate parts → export
STEP/STL/3MF/DXF → run every deterministic gate → write `design-report.json`), reads
each failing check, fixes the BRIEF, and reruns. The artifacts are projections of the
brief — never edit `.step/.stl/.3mf/.dxf`, `manifest.json`, `provenance.json`, or
`design-report.json` directly, and never weaken a process limit or threshold to pass.

Finally delegate to `mech-review` for an advisory pass: visual sanity of renders/DXF
outlines and parametric review of dimensions, fits, and mechanism rules. Its findings
are observations only — fold them back into the brief only through `mech_author`
re-runs or by asking the user.

Summarize for the user: the final `verdict`, each failing gate by id if any, the
artifact directory, and open follow-ups (e.g. machining drawings, FEA, or
manufacturer-specific DFM left to later stages).
