# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- `scripts/check_plugin_load.py` now asserts `post_tool_use` hooks (previously
  collected but unchecked) and renders the OK summary from the actual expected
  asset sets instead of a stale hardcoded string.

### Added

- `mech_render` / `python -m mech render`: rasterizes an exported `.dxf`
  to `.svg` (in-process `ezdxf` `SVGBackend`) and `.png`
  (`rsvg-convert`, `$MECH_RSVG_CONVERT` override; `librsvg2-bin` added to
  the tools image and the `apt` surface of the dependency checker). The
  MCP result attaches the PNG as `ImageContent` so vision models see the
  drawing inline, and `baseline_path` records/compares `image_sha256`
  (`recorded`/`match`/`diff`) as a deterministic visual change detector
  (ADR-0005).
- `src/mech/advisory.py`: typed `VisualReviewDetail`/`VisualFinding`/
  `AdvisoryResult` contract plus `parse_visual_review` for
  `review-visual-<slug>.advisory.json` records; the `mech-review` agent
  documents the convention (ADR-0005).
- `protect-generated` now guards `.svg`/`.png` writes; renders are
  projections of the brief like every other artifact.
- `e2e_authoring.py` renders each exported DXF (fail-open) and reports
  `renders`/`render_status` in the e2e payload.
- `mech-brief` declares the `record-vision-tool-event` post hook in
  frontmatter (plugin hooks do not propagate to task sub-agents).
- MCP tool metadata: every `mech_*` tool now carries `annotations.title`
  plus `readOnlyHint` / `destructiveHint` / `idempotentHint` /
  `openWorldHint` so MCP clients (including AgentCanvas) can rank and
  gate tool calls on honest write/read semantics.
- `mech-brief-rules` path-triggered skill: schema/provenance reminders
  injected whenever a `*.brief.json` / `*.intake.json` file is touched
  (complements the keyword skills; rules and keyword triggers are
  exclusive per skill).
- Docker image distribution: `docker/mech-tools.Dockerfile` (ubuntu:26.04 +
  uv-pinned Python 3.12 + `uv.lock` runtime), `mech-server` image built via
  the OpenHands SDK agent-server docker build, and the GHCR publish
  workflow `publish-mech-images.yml` with digest-lock
  (`docker/image-digests.json`) update PRs.
- `locked-image-check.yml`: weekly/post-publish smoke of the locked tools
  image (runs `e2e_authoring` inside the container).
- `examples/enclosure.brief.json` (used by docs and the image smoke check).
- Dependency checker coverage for Dockerfile `ARG` pins and the `ubuntu`
  base image tag.

### Changed

- `check_dependency_updates.py` now reports per-surface markdown tables
  (pypi direct, pypi-lock transitive drift, uv pin, Python versions,
  GitHub Actions, uvx pins, Docker ARG, Docker base) with `update
  available` / `deferred` / `up to date` states, lock-based `current`
  versions, `--markdown`/`--json` output flags, and deferral support via
  `scripts/dependency_update_deferrals.json`; the workflow posts this
  report directly.
- Docker action pins bumped: setup-buildx-action v4.4.1, login-action
  v4.6.0, build-push-action v7.4.0.
- build123d bumped to 0.13.0 via a `pillow>=12.3.0,<13`
  `override-dependencies` entry (threejs-materials' `pillow<12.3` cap
  conflicts with openhands-sdk's `pillow>=12.3`; the override is safe
  because threejs-materials only feeds viewer/material export).
- Deferred candidates recorded with re-check deadlines: mcp 2.x
  (fastmcp-slim requires `mcp<2`) and Python 3.14 (unverified SDK/OCP
  wheel support).

## [0.1.0] — unreleased

First public release (in preparation; no git tag published yet).

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

[Unreleased]: https://github.com/VibeBB/mechanical-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/VibeBB/mechanical-agent/releases/tag/v0.1.0
