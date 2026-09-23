---
description: Re-run all deterministic gates for an existing mechanical design.
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


Run `python3 "$MECH_PLUGIN/scripts/mech_launcher.py" gates --brief <brief.json> --out <out_dir>` and report the JSON
verdict verbatim. The gates re-generate the design and re-check kernel validity, STEP
round-trip, STL consistency, interference, board keepout, opening penetration, wall
thickness, DFM/mechanism/fit/stackup rules, and manifest hashes. A `fail` or
`unknown` check means the design is not done — fix the brief and re-run
`mech_author` (`python -m mech.cli author`) rather than editing artifacts.
