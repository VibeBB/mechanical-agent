# Hooks

`plugins/mech/hooks/hooks.json` registers all hook commands; each resolves
the plugin root via `$MECH_PLUGIN_ROOT` → `$OPENHANDS_PROJECT_DIR/plugins/mech`
→ `~/.agents/plugins/mech` → `~/.openhands/plugins/installed/mech`. Missing
scripts exit 0 (never block); `protect-generated` and `mech-doctor` fail
loud when the plugin root cannot resolve.

## session_start

| Hook | Script | Behavior |
|---|---|---|
| `mech-doctor` | `scripts/mech_launcher.py doctor --warn` | exit 0 always; prints environment probe as context (reads the toolchain, writes nothing) |
| `intake-attachments` | `hooks/scripts/intake_attachments.py` | exit 0; materializes user-attached intake files to `intake/attachments/<sha256[:12]>.<ext>` + `manifest.jsonl` (reads prompt attachments, writes intake dir) |
| `ensure-llm-profiles` | `hooks/scripts/ensure_llm_profiles.py` (shared, hash-locked) | exit 0; provisions LLM profiles incl. the vision profile (writes `~/.openhands/llm_profiles`) |
| `require-records` | `hooks/scripts/require_records.py session-start` (shared, hash-locked) | exit 0; writes `observations/mech/.sessions/<session>.json` marker |
| `report-ux-inbox` | `hooks/scripts/report_ux_inbox.py` | exit 0 always; reads `liaison/*.ux-request.json`, writes nothing; prints pending mech requests as `additionalContext` telling the agent to call `mech_ux_inbox`; silent when none |

## user_prompt_submit

| `intake-attachments` | same script — re-runs on every prompt |

## pre_tool_use

| Hook | Matcher | Behavior |
|---|---|---|
| `protect-generated` | `file_editor\|apply_patch\|terminal` | exit 2 (block) + stderr reason on a protected write; exit 0 otherwise. Protected: `.step/.stp/.stl/.3mf/.dxf/.dxf_lint.json/.svg/.png/.ux-response.json` suffixes and `manifest.json`, `provenance.json`, `design-report.json`, `decisions.jsonl`, `impressions.jsonl`, `vision-reviews.jsonl`, `records-status.json` — path arguments only, file bodies never scanned; terminal writes detected via redirects/cp/mv/dd/sed -i/rm/tee/mkdir/chmod... |
| `safety-rail` | `terminal` (shared, hash-locked) | exit 2 (block) on dangerous shell commands; exit 0 otherwise |

## stop

| `require-records` (first) | `require_records.py stop` | exit 2 (deny) while the session owes decisions / fresh stage impressions / vision reviews, bounded by `max_stop_denials: 2`; exit 0 when satisfied. Reads `observations/mech/*.jsonl` + artifact tree per `records-policy.json`; writes `records-status.json` |
| `report-design-status` | `report_design_status.py` | exit 0; prints each `design-report.json` verdict ≤ 3 dirs deep as context; names every failing check; flags rendered `.png` files that lack a `review-visual-*.advisory.json` until a vision review exists |
| `intake-attachments` | same intake script | exit 0 |

## post_tool_use

| Hook | Matcher | Behavior |
|---|---|---|
| `record-vision-tool-event` | `inspect_image_with_vision` | exit 0; appends `{sequence, event_id, question, profile_name, model, response_sha256, session_id}` to `vision-tool-events.jsonl` |
| `record-image-observation` | `file_editor\|mech_render\|mech_render_views\|mech_author` | exit 0; hashes every image path the tool touched/returned (including the inline `mech_author` views PNG) into `image-observations.jsonl` `{sequence, event_id, tool_name, image_path, image_sha256, recorded_at, session_id, actor, tool_call_id}` |

`_records.py` and `_provenance.py` are stdlib helper modules imported by
the hook scripts above (not hooks themselves). Shared files
(`ensure_llm_profiles.py`, `safety_rail.py`, `_provenance.py`,
`_records.py`, `require_records.py`) are canonical across the family and
hash-locked by `scripts/check_shared_hooks.py`.
