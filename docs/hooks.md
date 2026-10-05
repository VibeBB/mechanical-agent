# Hooks

`plugins/mech/hooks/hooks.json` registers all hook commands; each resolves
the plugin root via `$MECH_PLUGIN_ROOT` → `$OPENHANDS_PROJECT_DIR/plugins/mech`
→ `~/.agents/plugins/mech` → `~/.openhands/plugins/installed/mech`. Missing
scripts exit 0 (never block); `protect-generated` and `mech-doctor` fail
loud when the plugin root cannot resolve.

## session_start

| Hook | Script | Behavior |
|---|---|---|
| `mech-doctor` | `scripts/mech_launcher.py doctor --warn` | environment probe printed as context; `--warn` never fails |
| `intake-attachments` | `hooks/scripts/intake_attachments.py` | materializes user-attached intake files to `intake/attachments/<sha256[:12]>.<ext>` + `manifest.jsonl` |
| `ensure-llm-profiles` | `hooks/scripts/ensure_llm_profiles.py` (shared, hash-locked) | provisions LLM profiles incl. the vision profile |
| `require-records` | `hooks/scripts/require_records.py session-start` (shared, hash-locked) | writes `observations/mech/.sessions/<session>.json` marker |
| `report-ux-inbox` | `hooks/scripts/report_ux_inbox.py` | lists `liaison/*.ux-request.json` targeting mech without a sibling `.ux-response.json` as additional context; silent when none |

## user_prompt_submit

| `intake-attachments` | same script — re-runs on every prompt |

## pre_tool_use

| Hook | Matcher | Behavior |
|---|---|---|
| `protect-generated` | `file_editor|apply_patch|terminal` | rejects writes to generated artifacts: `.step/.stp/.stl/.3mf/.dxf/.dxf_lint.json/.svg/.png/.ux-response.json` suffixes and `manifest.json`, `provenance.json`, `design-report.json`, `decisions.jsonl`, `impressions.jsonl`, `vision-reviews.jsonl`, `records-status.json` — path arguments only, file bodies never scanned; terminal writes detected via redirects/cp/mv/dd/sed -i/rm/tee/mkdir/chmod... |
| `safety-rail` | `terminal` (shared, hash-locked) | blocks dangerous shell commands |

## stop

| `require-records` (first) | `require_records.py stop` | denies finishing while the session owes decisions / fresh stage impressions / vision reviews, bounded by `max_stop_denials: 2`; writes `records-status.json` |
| `report-design-status` | `report_design_status.py` | prints each `design-report.json` verdict ≤ 3 dirs deep as context; names every failing check |
| `intake-attachments` | same intake script |

## post_tool_use

| Hook | Matcher | Behavior |
|---|---|---|
| `record-vision-tool-event` | `inspect_image_with_vision` | appends `{sequence, event_id, question, profile_name, model, response_sha256, session_id}` to `vision-tool-events.jsonl` |
| `record-image-observation` | `file_editor|mech_render|mech_render_views` | hashes every image path the tool touched/returned into `image-observations.jsonl` |

`_records.py` and `_provenance.py` are stdlib helper modules imported by
the hook scripts above (not hooks themselves). Shared files
(`ensure_llm_profiles.py`, `safety_rail.py`, `_provenance.py`,
`_records.py`, `require_records.py`) are canonical across the family and
hash-locked by `scripts/check_shared_hooks.py`.
