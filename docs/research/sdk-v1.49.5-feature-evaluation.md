# Research note: OpenHands SDK v1.49.5 feature evaluation for mech

Checked on: 2026-09-23 (PyPI openhands-sdk 1.49.5, released 2026-09-23;
openhands-tools 1.49.5)

## Scope

mech consumes the SDK only as a plugin boundary (`plugins/mech`) plus the
`sdk-check` dependency group used by the `plugin-load` CI job. Features
that require runtime code (conversation orchestration, workspace
management, settings) are out of scope by design — the plugin declares
behavior, the host app executes it. The `mech` MCP server is a stdio
boundary over the deterministic `python -m mech` entry points.

## v1.49.4 → v1.49.5 delta

| Change | mech relevance |
| --- | --- |
| `openhands/sdk/utils/masking.py` — `PreserveDataUrls` / `SkipSecretMasking` context managers | positive — image `data:` URLs are no longer secret-masked; mech's PNG/render projections stay intact when a vision-capable model inspects them via `inspect_image_with_vision` |
| `message.py` `image_urls` gains `PreserveDataUrls` | positive — same as above, on the message construction path |
| `mcp/tool.py` normalizes mcp 2.x snake_case ↔ camelCase wire keys | none now — `mcp` stays on 1.30.0 (`fastmcp<4` → `mcp<2.0`); the normalization is forward-compat for when the cap lifts |
| `openhands-tools` `browser_use` `screenshot_data` gets `SkipSecretMasking` | none — mech declares no browser tooling |
| `model_features.py` adds `gpt-6` family and `gpt-5.2-codex` | none — agents use `model: inherit` |
| `telemetry.py` adds `UsageSnapshot` | none — runtime surface, not plugin boundary |
| extensions metadata utf-8 fix | none — no extension assets |

## Evaluated features

| Feature | Decision | Rationale |
| --- | --- | --- |
| MCP `ToolAnnotations` (`title`, `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) | **adopted** | Every `mech_*` tool now declares honest read/write hints so MCP clients (AgentCanvas and other hosts) can gate calls. `mech_author`, `mech_gates`, and `mech_export_envelope` write artifacts/reports; the rest are read-only/idempotent/closed-world. |
| MCP tool `outputSchema` / `structuredContent` | not adopted | All tools return a `CallToolResult` JSON text envelope; a typed output schema duplicates the per-tool contracts already documented in the input schemas and docs. Deferred until a client requires it. |
| `paths:` (PathTrigger) skill rules | **adopted** | New `mech-brief-rules` skill fires on `*.brief.json`/`*.intake.json` touch — the same pattern wire-agent adopted (`wire-contract-rules`). Keyword skills remain model-invocable; the mechanisms are exclusive per skill. |
| Vision path (`inspect_image_with_vision`, post_tool_use vision record hook) | already adopted | `mech-review`/`mech-brief` use the vision-event record hook and the saved-profile delegation pattern; vision stays L2-only per ADR-0003. |
| `prompt`/`agent` hook types | not adopted | Non-`command` hook types inject non-deterministic text/agent loops; the deterministic/fail-closed invariant keeps hooks stdlib `command` only. |
| `SessionEnd`/`UserPromptSubmit` hook events | not adopted | Current `session_start` + `pre_tool_use` + `post_tool_use` + `stop` coverage matches the doctor/guard/vision-record/status design; no new automation surface needed. |
| AgentCanvas | no action | `@openhands/agent-canvas` connects over ACP and installs plugins under `~/.openhands/plugins/installed/` — already covered by the plugin-root resolution order. Tool annotations improve how the canvas displays `mech_*` tools. |
| plugin.json `$schema` | not adopted | The 1.0.0 plugin schema field is tolerated-but-unenforced by the SDK loader (`extra="allow"`); adding it is cosmetic. Revisit when the loader starts validating. |

## Verification record

- `uv run python scripts/verify_all.py --stage fast`: pass — includes the
  new `test_mcp_tool_annotations` and `test_brief_rule_is_path_triggered`
  assertions.
- `uv run --group sdk-check python scripts/check_plugin_load.py`: OK —
  SDK v1.49.5 loads the plugin; `EXPECTED_SKILLS` now includes
  `mech-brief-rules`.
- `uv run python scripts/check_dependency_updates.py`: clean except the
  recorded `mcp 2.x` and Python 3.14 deferrals.
