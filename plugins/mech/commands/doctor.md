---
description: Diagnose the mech CAD runtime (build123d/OCP, exporters).
allowed-tools:
  - terminal
---

Run `python3 -m mech.cli doctor` and report its JSON result without changing or
weakening any check. Use `python3 -m mech.cli doctor --warn` for session startup
diagnostics where findings must not block the session.
