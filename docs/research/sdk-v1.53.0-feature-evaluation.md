# OpenHands SDK v1.53.0 feature evaluation (mechanical-agent)

Scope: `openhands-sdk` and `openhands-tools` move from 1.52.0 to 1.53.0
(GitHub release 2026-10-05; both wheels published on PyPI). The complete
upstream range `v1.52.0..v1.53.0` (6 PRs, from the release notes plus a
source diff of both tags) was reviewed. No other component moved in this
update.

Primary sources: [OpenHands SDK v1.53.0 release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.53.0),
[v1.52.0...v1.53.0 compare](https://github.com/OpenHands/software-agent-sdk/compare/v1.52.0...v1.53.0).

## SDK 1.52.0 -> 1.53.0

| Upstream change | Decision | Evaluation |
| --- | --- | --- |
| #5024 fix(skills): exclude installed packages from the user skills scan | adopted implicitly | SDK-internal fix in `openhands/sdk/skills/skill.py`; skills inside the managed installed-packages dir no longer leak into the user-skill merge. Plugin skills and `Plugin.load` are unaffected — `check_plugin_load.py` confirms on 1.53.0. |
| #5479 feat(agent-server): serve a manifest-declared SVG icon for canvas extensions | available, not adopted | New optional `icon` field on `CanvasExtensionManifest` (package-root-relative .svg path, containment-checked), served at `GET /canvas_extensions/installed/{name}/icon` with a CSP-sandboxed FileResponse. VibeBB plugins are AgentCanvas plugins (`.plugin/plugin.json`), not canvas extensions — nothing declares a canvas-extension entrypoint manifest. Revisit only if a repo ships a canvas extension. |
| #5476 fix(ci): pin the TypeScript client's Agent Server in the release PR | not applicable | Upstream release CI only. |
| #5512 fix(ci): read the unreleased Agent Server contract from source on release PRs | not applicable | Upstream release CI only. |
| #5513 docs: refresh AGENTS.md guidance | not applicable | Upstream docs only. |
| #4782 chore: weekly test sweep removes low-value coverage | not applicable | Upstream tests only. |
| fastmcp `>=3.2.0,<4`, pydantic `>=2.13.5`, pillow `>=12.3.0`, requires-python `>=3.12` unchanged | n/a | The SDK's constraint surface is identical to 1.52.0 — verified by diffing the v1.52.0 and v1.53.0 tags: `openhands-sdk`, `openhands-tools` and `openhands-agent-server` pyproject.tomls differ only in `version = "1.53.0"`. `check_plugin_load.py` confirms `Plugin.load` and the tool registry still pass on 1.53.0. The `pillow>=12.3.0,<13` override (threejs-materials<1.3 conflict) stays valid — the SDK's pillow bound did not move. |

## Compatibility deferrals

MCP 2.x remains deferred: installed `openhands-sdk` 1.53.0 metadata still
requires `fastmcp>=3.2.0,<4`, which caps `mcp<2` (latest 2.3.0). The
deferral entry in `scripts/dependency_update_deferrals.json` now cites
openhands-sdk 1.53.0; `review_by` kept at 2027-04-01. The
`openhands-agent-server` image tag `1.53.0-python` is available upstream;
`docker/image-digests.json` is written only by `publish-mech-images.yml`
and is not edited here — the server-image bump lands with the next
publish, and cleared `.trivyignore` waivers get dropped on the rescan.

## Server-image build notes (verified for v1.53.0)

- `publish-mech-images.yml` derives `SDK_VERSION` from the
  `openhands-sdk==` pin in `[project].dependencies` and clones
  `OpenHands/software-agent-sdk` at that tag — this bump moves the
  agent-server build to v1.53.0 automatically at the next publish; no
  workflow or lock edit is needed.
- The SDK root `uv.lock` at v1.53.0 still pins fsspec 2025.9.0, so the
  workflow's "Bump SDK fsspec for CVE-2026-104851" step stays needed
  as-is.
- The agent-server `build.py` registry cache-tag needle
  `buildcache-{self.target}-{self.base_image_slug}{self.flavor_suffix}`
  is unchanged at v1.53.0, so the stabilize-cache patch still applies.
