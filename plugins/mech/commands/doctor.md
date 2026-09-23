---
description: Diagnose the mech CAD runtime (build123d/OCP, exporters).
allowed-tools:
  - terminal
---
Inside OpenHands, mech commands run inside the pinned tools image via the
plugin launcher. Resolve the plugin root the same way the hooks do
(`$MECH_PLUGIN_ROOT`, `${OPENHANDS_PROJECT_DIR}/plugins/mech`,
`~/.agents/plugins/mech`, `~/.openhands/plugins/installed/mech`) into
`$MECH_PLUGIN`, then call `python3 "$MECH_PLUGIN/scripts/mech_launcher.py"
<args>`. In a repo checkout, `uv run python -m mech <args>` is equivalent.


Run `python3 "$MECH_PLUGIN/scripts/mech_launcher.py" doctor` and report its JSON result without changing or
weakening any check. Use `python3 "$MECH_PLUGIN/scripts/mech_launcher.py" doctor --warn` for session startup
diagnostics where findings must not block the session.
