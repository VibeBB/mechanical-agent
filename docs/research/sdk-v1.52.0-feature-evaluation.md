# OpenHands SDK v1.52.0 feature evaluation (mechanical-agent)

Scope: `openhands-sdk` and `openhands-tools` move from 1.51.0 to 1.52.0
(PyPI upload 2026-10-04). The complete upstream range `v1.51.0..v1.52.0`
(19 commits) was reviewed. No other component moved in this update.

Primary sources: [OpenHands SDK v1.52.0 release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.52.0),
[v1.51.0...v1.52.0 compare](https://github.com/OpenHands/software-agent-sdk/compare/v1.51.0...v1.52.0).

## SDK 1.51.0 -> 1.52.0

| Upstream change | Decision | Evaluation |
| --- | --- | --- |
| #4630 fix: drop in-flight tool calls from `ask_agent` context | adopted implicitly | Sub-agent context fix inside the SDK; plugin agents delegate via `task_tool_set` and inherit the corrected context with the pin. |
| #5363 fix(client): retry a lost create only where the server deduplicates; #5362 fix(server): dedupe concurrent conversation creates and forks | rides the image + library | Client/server robustness; the library half lands with the pin, and the server half arrives when `publish-mech-images.yml` rebuilds mech-server at tag v1.52.0. |
| #5462 feat: propagate automation observability context | not adopted | The plugin runs under a user/AgentCanvas session, not an OpenHands automation; no adoption surface. |
| #5485 fix(terminal): isolate tmux sockets to prevent cross-conversation handle reuse | adopted implicitly | Terminal-session isolation fix inside the SDK tools layer; lands with the pin. |
| #5209 fix(workspace): publish Docker ports on loopback | not adopted | Security hardening of SDK-managed remote workspaces; mech tool execution runs inside the locked `mech-tools` image. |
| #5403 fix(agent-server): release terminal run permits promptly | rides the image | Agent-server runtime fix; arrives with the next `v1.52.0`-based mech-server publish. |
| #5348 feat(agent-server): stop operation for a single BashCommand | available, not adopted | New server endpoint; the plugin does not call agent-server REST directly. |
| #5421 python-frontmatter 1.1.0 -> 1.3.0, #5420 uvicorn 0.52.4 -> 0.54.0, #5423 posthog 6.7.7 -> 7.60.0 | not applicable | Dependencies of `openhands-agent-server`, not of `openhands-sdk`/`openhands-tools`; they do not appear in this repo's lockfile. |
| #5426 typescript-eslint, #5424 prettier, #5427 @types/node, #5422 actions/checkout, #5472 TS agent-server version, #5494 example tmux socket paths, #5490 release | not applicable | TypeScript-client/CI/example housekeeping; this repo does not use the TS client. |
| fastmcp `>=3.2.0,<4`, pydantic `>=2.13.5`, pillow `>=12.3.0`, requires-python `>=3.12` unchanged | n/a | The SDK's constraint surface is identical to 1.51.0; `check_plugin_load.py` confirms `Plugin.load` and the tool registry still pass on 1.52.0. The `pillow>=12.3.0,<13` override (threejs-materials<1.3 conflict) stays valid — the SDK's pillow bound did not move. |

## Compatibility deferrals

MCP 2.x remains deferred: installed `openhands-sdk` 1.52.0 metadata still
requires `fastmcp>=3.2.0,<4`, which caps `mcp<2` (latest 2.3.0). The
deferral entry in `scripts/dependency_update_deferrals.json` now cites
openhands-sdk 1.52.0; `review_by` kept at 2027-04-01. The
`openhands-agent-server` image tag `1.52.0-python` is available upstream;
`docker/image-digests.json` is written only by `publish-mech-images.yml`
and is not edited here — the server-image bump lands with the next
publish, and cleared `.trivyignore` waivers get dropped on the rescan.
