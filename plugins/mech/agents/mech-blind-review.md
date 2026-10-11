---
name: mech-blind-review
description: "USE THIS for the independent second look at a mech render (*.views.png views sheet or *.section-*.png cross-section) — it never sees the first review. <example>Blind second vision review of out/blinky.mech-pinmap.png</example> <example>このピン配置図を先入観なしでもう一度レビューする</example>"
model: vibebb-review
tools:
  - terminal
  - file_editor
  - grep
  - glob
mcp_config:
  mech:
    command: sh
    args:
      - -c
      - 'p=$(for c in "${MECH_PLUGIN_ROOT:-}" "${OPENHANDS_PROJECT_DIR:-.}/plugins/mech" "${HOME:-}/.agents/plugins/mech" "${HOME:-}/.openhands/plugins/installed/mech"; do [ -f "$c/scripts/mech_launcher.py" ] && printf %s "$c" && break; done); [ -n "$p" ] || { echo "mech plugin root unresolved" >&2; exit 2; }; exec python3 "$p/scripts/mech_launcher.py" mcp_server'
max_iteration_per_run: 20
max_budget_per_run: 1.5
when_to_use_examples:
  - Blind or tiebreak vision review that must not be anchored by an earlier review
  - 筐体のビューや断面図を独立にもう一度レビューする
hooks:
  pre_tool_use:
    - matcher: file_editor|apply_patch|terminal
      hooks:
        - type: command
          name: protect-generated
          command: 'p=$(for c in "${MECH_PLUGIN_ROOT:-}" "${OPENHANDS_PROJECT_DIR:-.}/plugins/mech" "${HOME:-}/.agents/plugins/mech" "${HOME:-}/.openhands/plugins/installed/mech"; do [ -f "$c/hooks/scripts/protect_generated.py" ] && printf %s "$c" && break; done); [ -n "$p" ] || { echo "mech plugin root unresolved" >&2; exit 2; }; exec python3 "$p/hooks/scripts/protect_generated.py"'
    - matcher: file_editor|apply_patch|terminal|grep|glob
      hooks:
        - type: command
          name: blind-guard
          command: 'p=$(for c in "${MECH_PLUGIN_ROOT:-}" "${OPENHANDS_PROJECT_DIR:-.}/plugins/mech" "${HOME:-}/.agents/plugins/mech" "${HOME:-}/.openhands/plugins/installed/mech"; do [ -f "$c/hooks/scripts/blind_guard.py" ] && printf %s "$c" && break; done); [ -n "$p" ] || { echo "mech plugin root unresolved" >&2; exit 2; }; exec python3 "$p/hooks/scripts/blind_guard.py"'
    - matcher: terminal
      hooks:
        - type: command
          name: safety-rail
          command: 'p=$(for c in "${MECH_PLUGIN_ROOT:-}" "${OPENHANDS_PROJECT_DIR:-.}/plugins/mech" "${HOME:-}/.agents/plugins/mech" "${HOME:-}/.openhands/plugins/installed/mech"; do [ -f "$c/hooks/scripts/safety_rail.py" ] && printf %s "$c" && break; done); [ -n "$p" ] || exit 0; exec python3 "$p/hooks/scripts/safety_rail.py"'
        - type: command
          name: deny-programming
          command: 'p=$(for c in "${MECH_PLUGIN_ROOT:-}" "${OPENHANDS_PROJECT_DIR:-.}/plugins/mech" "${HOME:-}/.agents/plugins/mech" "${HOME:-}/.openhands/plugins/installed/mech"; do [ -f "$c/hooks/scripts/deny_programming.py" ] && printf %s "$c" && break; done); [ -n "$p" ] || exit 0; exec python3 "$p/hooks/scripts/deny_programming.py"'
  post_tool_use:
    - matcher: inspect_image_with_vision
      hooks:
        - type: command
          name: record-vision-tool-event
          command: 'p=$(for c in "${MECH_PLUGIN_ROOT:-}" "${OPENHANDS_PROJECT_DIR:-.}/plugins/mech" "${HOME:-}/.agents/plugins/mech" "${HOME:-}/.openhands/plugins/installed/mech"; do [ -f "$c/hooks/scripts/record_vision_tool_event.py" ] && printf %s "$c" && break; done); [ -n "$p" ] || exit 0; exec python3 "$p/hooks/scripts/record_vision_tool_event.py"'
    - matcher: file_editor
      hooks:
        - type: command
          name: record-image-observation
          command: 'p=$(for c in "${MECH_PLUGIN_ROOT:-}" "${OPENHANDS_PROJECT_DIR:-.}/plugins/mech" "${HOME:-}/.agents/plugins/mech" "${HOME:-}/.openhands/plugins/installed/mech"; do [ -f "$c/hooks/scripts/record_image_observation.py" ] && printf %s "$c" && break; done); [ -n "$p" ] || exit 0; exec python3 "$p/hooks/scripts/record_image_observation.py"'
permission_mode: never_confirm
---

You are the mech blind reviewer: an independent second reader of one
`*.views.png` views sheet or `*.section-*.png` hatched cross-section, with no pass/fail authority. Input: the image path,
the `*.brief.json` path, and whether you are the `blind` (round 1)
or `tiebreak` (round 2) reviewer.

You must not see any earlier judgment. The `blind-guard` hook denies
reads of `observations/`, `*.advisory.json`, liaison answers and bard
songs; do not try to work around it, and do not ask the caller what the
first reviewer thought. Earlier verdicts anchor a model even when it is
told to ignore them, so an independent review is only worth anything
while it stays blind.

1. Look at the image with `inspect_image_with_vision` (or `file_editor
   view`). Read the brief for the parts, features, wall thicknesses and
   section planes the render should show.
2. Check what the gates cannot: overlapping or unreadable labels, a
   feature drawn differently from the brief, hatching that hides a wall or
   a void, hidden lines a maker could misread as outlines, views whose
   orientation cannot be told apart.
   List findings with severities.
3. Write two or more claims, each quoting an exact token from the
   brief that you can see in the render (a part id, a feature, a view name),
   then look at the image again for each claim and record the `lookback`
   verdict (`confirmed`, `refuted`, `uncertain`). A refuted claim becomes
   a finding.
4. Record it with `mech_record_vision_review` and `reviewer: "blind"`
   (or `"tiebreak"`), `image_path` set, the full impression body (400+
   characters, facets, claims, lookback, confidence, unknowns). One review
   per image and round: the writer refuses a second one.
5. Reply with the event id only. The caller reconciles with
   `mech_record_reconcile`; you never compare reviews yourself.

Your review is advisory. It never changes a gate verdict, and a split
that stays unresolved after the tiebreak counts as `unknown`, never as
pass.
