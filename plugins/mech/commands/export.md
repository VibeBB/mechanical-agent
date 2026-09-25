---
description: Export CAD artifacts (STEP/STL/3MF/DXF) for an existing design brief.
argument-hint: <brief.json> <out_dir>
allowed-tools:
  - terminal
---
Inside OpenHands, mech commands run inside the pinned tools image via the
plugin launcher. Resolve the plugin root the same way the hooks do
(`$MECH_PLUGIN_ROOT`, `${OPENHANDS_PROJECT_DIR}/plugins/mech`,
`~/.agents/plugins/mech`, `~/.openhands/plugins/installed/mech`) into
`$MECH_PLUGIN`, then call `python3 "$MECH_PLUGIN/scripts/mech_launcher.py"
<args>`. In a repo checkout, `uv run python -m mech <args>` is equivalent.


Run `python3 "$MECH_PLUGIN/scripts/mech_launcher.py" export --brief <brief.json> --out <out_dir>` to regenerate the
parts and write the assembly STEP, per-part STEP/STL/DXF, the combined 3MF,
`manifest.json` (per-file sha256), and `provenance.json`. Export does not run gates —
use `/mech:gates` or `mech_author` when a verdict is needed. Never write artifacts to
paths the protect-generated hook protects by hand-editing; always export.

An image you inspect visually is an observation, not a verdict: persist it
as `review-visual-<slug>.advisory.json` with the `review-record` subcommand
(`--image`, `--model`, `--checklist`, `--impression`, `--findings`,
`--summary`), the same record `mech-review` writes — never hand-assembled
JSON. Every rendered raster must be vision-inspected — required, not
optional — and the impression is a substantive multi-sentence reading of
what the sheet communicates well and what it leaves unsaid (the validator
rejects records under 240 characters or with fewer than two sentences).
This applies whether the review ran through `mech-review` or inline here.
