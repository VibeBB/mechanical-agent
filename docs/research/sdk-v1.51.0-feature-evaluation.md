# OpenHands SDK v1.51.0 feature evaluation (mechanical-agent)

Scope: `openhands-sdk` and `openhands-tools` move from 1.50.1 to 1.51.0
(PyPI release 2026-10-03T07:38Z; upstream range `v1.50.1..v1.51.0`,
18 commits, reviewed in full). uv moves 0.12.21 -> 0.12.22 in the same
round; `anchore/sbom-action` was already at v0.24.3 (PR #111); ruff was
already at 0.16.10 in `uv.lock`.

Primary source:
[OpenHands SDK v1.51.0 release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.51.0),
[uv 0.12.22 release](https://github.com/astral-sh/uv/releases/tag/0.12.22),
[anchore/sbom-action v0.24.3 release](https://github.com/anchore/sbom-action/releases/tag/v0.24.3).

## SDK 1.50.1 -> 1.51.0

| Upstream change | Decision | Evaluation |
| --- | --- | --- |
| #5151 agent-profiles: `tools` is the only tool control, selected from one server catalog | not adopted | VibeBB plugins keep their own tool contract; the mech plugin's tool set is its `.mcp.json` + `mech` package, not SDK agent-profiles. |
| #5449 agent-profiles: a profile can replace the agent's persona | not adopted | Persona/profile machinery is unused; mech agents are fixed AgentDefinitions delegating to `python -m mech`. |
| #5450 loaded tools supply their system-prompt guidance (browser) | not adopted | The browser tool is not loaded by this plugin; guidance stays in plugin Markdown agents/skills. |
| #5358 agent-profiles: delegated sub-agents stay within the profile's tools and MCP servers | not adopted | Sub-agency here is `task`/`TaskToolSet` with per-agent hook declarations, not SDK profile delegation. |
| #5406 agent-profiles: launch every agent through resolve and finalize | adopted implicitly | Internal launch-path unification; `scripts/check_plugin_load.py` exercises the same agent path and passes under 1.51.0. |
| #5332 `prompt_cache_key` resolved via real provider for proxied models | adopted with the pin | Bug fix on the LLM path; benefits proxied deployments without repo changes. |
| #5274 OpenRouter becomes a verified provider | adopted with the pin | Provider-catalog addition; no constraint on existing providers. |
| #5412 send system+user classifier messages for direct-routing | adopted with the pin | Routing correctness fix; no repo surface. |
| #5434 deprecate `ACPAgentSettings.llm` so ACP agents keep their metrics LLM | adopted with the pin | Settings cleanup; this repo does not override ACP settings. |
| #5417 agent-server: resolve provider connection in `/switch_llm` | rides the image | mech-server is assembled from `sdk:openhands-agent-server/v${SDK_VERSION}` by `publish-mech-images.yml`; the fix arrives with the next publish at tag v1.51.0 — no committed lock is edited. |
| #1326 fix `find_dotenv` assertion error in local conversation | adopted with the pin | Local-conversation robustness fix on the path the plugin-load check exercises. |
| #5419 pydantic 2.12.5 -> 2.13.5 | already in lock | `uv.lock` already resolved pydantic 2.13.5 within the `pydantic>=2` floor before this round. |
| #4945, #5415 upstream CI fixes | not applicable | Upstream repository CI only. |
| #5425, #5428 TypeScript client bumps | not applicable | This repository does not use the SDK TypeScript client. |
| #5397 stress-test run-slot fix | not applicable | Upstream test-only change. |
| #5470 release | not applicable | Release housekeeping. |

## uv 0.12.21 -> 0.12.22

| Upstream change | Decision | Evaluation |
| --- | --- | --- |
| CPython 3.10.22/3.11.17/3.12.15/3.13.16/3.14.8 builds added | inherent | The tools image runs `uv python install 3.12`; the next published image picks up 3.12.15 automatically. No pin change (image installs "3.12" minor). |
| Workspace-member default groups / dependency-group Python requirements recorded in lockfiles; frozen-sync honors them | not applicable | This repository is a single project, not a uv workspace. |
| `UV_PYTHON_ARCH` config | not adopted | Only one architecture is installed; version-only selection suffices. |
| `--no-default-groups` honored by `uv audit` (preview) | not adopted | The repo does not run `uv audit`. |
| Wheel platform-tag uppercase suffixes accepted; `--offline` hidden from `uv publish` help; embedded metadata compression shrinks the binary | inherent | Resolver/packaging robustness; nothing to configure. |
| Relock verifies unchanged requirements against existing lockfile hashes | inherent | Makes `uv lock --upgrade` results more reproducible. |
| MSRV raised to Rust 1.97 | not applicable | Prebuilt binaries are used. |

## anchore/sbom-action -> v0.24.3

Already applied by PR #111 (`v0.24.2` -> `v0.24.3`, commit
`66cbf4bc1f1c0d2edc94016e65bc221b6bb0ad6c`). Upstream release is dev-
dependency/toolchain bumps only (eslint, type-fest, tsx, zizmor-action,
go-make); no action-input or runtime-behavior change, so nothing to
adopt beyond the pin that already landed.

## ruff

Already at 0.16.10 in `uv.lock` before this round (`ruff>=0.16` dev
floor). `uv lock --upgrade` produced no ruff change; no new diagnostics
in `verify_all --stage fast`.

## mcp (stays deferred)

`mcp>=1.29,<2` unchanged. Installed SDK metadata still requires
`fastmcp>=3.2.0,<4` (resolved `fastmcp-slim==3.4.7`), which caps
`mcp<2.0`. Deferral refreshed: latest `2.3.0`, reason now references
openhands-sdk 1.51.0; `review_by` kept at 2027-04-01.

## Transitive `uv.lock` drift (50 entries)

All drift is transitive under the direct pins — no repo-owned spec
changed. Semver-major moves verified non-breaking for this repo:
`cyclopts` 4 -> 5 and `openapi-pydantic` 0.5 -> 0.6 resolve inside
`fastmcp-slim` 3.4.7's own constraints; `deprecated` 1 -> 3 inside
OpenTelemetry's. `threejs-materials` 1.2.4 still caps `pillow<12.3.0`,
so the `[tool.uv] override-dependencies` pillow override stays required.
New `h2`/`hpack`/`hyperframe` entries arrive via an httpx http2 extra on
the SDK side. Font rendering (`fonttools` 4.66.1) rides build123d's
bound and is exercised by the DXF/render tests in the fast stage.
Everything else (litellm, opentelemetry, google-*, boto3, posthog,
fakeredis, ollama, sse-starlette, uvicorn, huggingface-hub, nodeenv,
rich-rst, and patch bumps) is SDK/dev-internal and covered by
`check_plugin_load.py` + `verify_all --stage fast`.

## mech-server image / Trivy waivers

The satisfied `pypi` deferral for `openhands-sdk` (gate on this
changelog review) is removed from
`scripts/dependency_update_deferrals.json`. The ~70 upstream-borne
`.trivyignore` waivers enumerated against the `v1.50.1`-based mech-server
scan are kept: they stay valid until their `exp:` dates and are re-
evaluated by the publish-time Trivy gates and weekly `container-audit`
once the `v1.51.0`-based image lands — cleared waivers get dropped on
that re-scan, not in this pin bump.
