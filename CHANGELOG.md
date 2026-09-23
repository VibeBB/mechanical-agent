# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] — first release

### Added

- Deterministic core (`src/mech`): design brief + intake schemas, parametric
  generators for enclosures (screw/snap lid, board keepout, standoffs,
  openings, vents), brackets (plate/L/U + gussets), and spur gears;
  mechanism features (snap-fit, rib, boss modeled; living hinge, detent
  parametric); DFM rules for FDM/machining/molding/sheet-metal; ISO 286
  limits-and-fits; 1-D worst-case + RSS stackups; ISO thread and bearing
  seat tables.
- Gate runner: kernel validity, STEP round-trip, mesh validity,
  interference, board envelope, openings residual material, wall thickness,
  parametric/DFM/mechanism/fit/stackup checks, manifest sha256 — all
  fail-closed (`unknown` fails the design).
- Exporters: STEP (assembly + per part + references), STL, 3MF, DXF
  outlines, `manifest.json` (sha256), `provenance.json`, `design-report`
  (JSON + Markdown).
- OpenHands plugin (`plugins/mech`): six skills, three task sub-agents
  (`mech-brief`, `mech-design`, `mech-review` incl. vision-aided render
  review), four commands, hooks (session doctor, generated-artifact
  protection, design-status stop hook, vision event record), and the `mech`
  stdio MCP server.
- Scripts: `verify_all.py` (docs/fast stages, barrier + parallel jobs),
  `verify_docs.py`, `e2e_authoring.py`, `check_plugin_load.py`,
  `check_dependency_updates.py`, `bump_version.py`.
- CI: verify matrix (3.12/3.13), plugin-load, zizmor workflow lint, weekly
  dependency-update report, manual release workflow, dependabot.
