# Records and vision (VRP for mech)

The VibeBB Record Protocol is the family-wide way to keep the reasoning
behind a product; wire-agent holds the canonical spec
(`docs/records-protocol.md` there) and mech carries a byte-for-byte copy
of the shared hook pair plus its own typed writers in
`src/mech/records.py`. This page maps the protocol onto mech's stages.

## Logs

All logs live under `observations/mech/` (`records_dir` in
`plugins/mech/hooks/records-policy.json`), append-only JSONL:

| File | Kind | Written when |
|---|---|---|
| `decisions.jsonl` | `decision` | every non-trivial design choice, unprompted |
| `impressions.jsonl` | `stage_impression` | at the end of every stage, after the last regeneration |
| `vision-reviews.jsonl` | `vision_review` | every time the model looks at an image |
| `vision-tool-events.jsonl` | (hook) | `inspect_image_with_vision` answers (`record_vision_tool_event.py`) |
| `image-observations.jsonl` | (hook) | images returned by `file_editor` view / `mech_render` / `mech_render_views` (`record_image_observation.py`) |
| `records-status.json` | (hook) | last Stop-hook verdict and what is still owed |

`plugins/mech/hooks/records-policy.json` sets `max_stop_denials: 2` and
the artifact globs that must be covered by a fresh impression
(`*.brief.json`, `*.intake.json`, `design-report.*`, `*.envelope.json`,
`*.step/.stl/.3mf/.dxf`, `*.ux-response.json`; `examples/`, `tests/`,
`.devin/` ignored).

## Mech stages and the records they leave

| Stage | Agent | Records owed |
|---|---|---|
| intake | mech-brief | decision per resolved trade-off (e.g. which requirement interpretation), `intake_image` vision review per attached image read, stage impression bound to `*.intake.json`/`*.brief.json` |
| brief/author | mech-design | decision per non-trivial choice — process, material, wall thickness, closure type, fits, tolerances, mount strategy — impression bound to the out dir after the final `mech_author` regeneration, `assembly_render` vision review of every `*.views.png` |
| review | mech-review | `dxf_outline` vision review per rendered drawing, `part_render`/`assembly_render` per views sheet, impression bound to review outputs |
| liaison | any | `done` responses must carry `decision_refs` + `impression_refs` into these logs |

## Decision rules (enforced by `src/mech/records.py` and the shared hook mirror)

slug `id`/`stage`; `question` ≥ 10 chars; ≥ 1 `principles[]` entry ≥ 12
chars each (first principles / laws / standards); ≥ 2 `options[]` with
unique names and ≥ 1 `pros`/`cons`; `chosen` names an option;
`rationale` ≥ 200 chars; ≥ 1 `evidence[]` (`{path, sha256}` — directories
hash as a sorted tree — or `{reference}`); `risks[]` ≥ 1; `revisit_when`
required; `decided_by` `agent|user`.

## Impression rule

`impression` needs ≥ 400 characters, ≥ 3 sentence terminators (`.`/`!`/`?`
or `。`/`！`/`？`) and ≥ 3 distinct sentences. The same rule applies to
`impressions.jsonl`, `vision-reviews.jsonl` and the advisory
`review-visual-*.advisory.json` record (`src/mech/advisory.py` imports
`impression_is_prose`).

## Vision points (every image gets a `vision_review`)

- intake images (user sketches/photos) — `intake_image` checklist;
Every image the model looks at needs a `vision_review` record; the
sheet below lists each vision point, who reviews it, the checklist
value, and when:

| Vision point | Produced by | Reviewed by | Checklist | When |
| --- | --- | --- | --- | --- |
| Intake images (photos, sketches) | user attachments / `intake-attachments` hook | mech-brief | `intake_image` | at intake, before writing A*/Q* |
| DXF renders (`*.dxf` → `.png`) | `render_dxf` / author-time renders | mech-review (every one); mech-design for its own exports | `dxf_outline` | after export/author, before review sign-off |
| Part views sheets (`<part>.views.png`) | `render_views` / author-time renders | mech-review (every one) | `part_render` | after export/author |
| Assembly views sheet (`<name>.views.png`) | `render_views`; `mech_author` returns it inline | mech-design (self-check before handoff) and mech-review | `assembly_render` | after `verdict: pass` |
| Envelope anchor overlay | `render_views --envelope <name>.envelope.json` (marks per anchor, in all four views) | mech-design / mech-review | `assembly_render` | when anchors exist and the provenance sidecar was written |

Every `vision_review` impression judges geometric accuracy, ambiguity,
design intent, usefulness to maker/user, and the next step —

- `*.views.png` STEP views sheets — `part_render` (one part) or
  `assembly_render` (the assembly);
- DXF→PNG drawing renders — `dxf_outline`;
- any `inspect_image_with_vision` call — bound via `source_event_id`.

Each review judges geometric accuracy, ambiguity, whether the design
intent comes across, usefulness to the maker or user, and the next step —
not only legibility. `mech_render` and `mech_render_views` return the PNG
inline (ImageContent) so a vision model sees the actual bytes; the
`python -m mech review-record` CLI additionally mirrors the advisory
record into `vision-reviews.jsonl`.

## Enforcement

`require_records.py session-start` marks the session; `require_records.py
stop` (first stop hook) denies finishing while this session owes a
decision, a fresh stage impression for changed artifacts (recorded sha256
must equal current bytes), or a vision review for every vision event /
viewed image — bounded by `max_stop_denials`. `records-status.json`
records the last verdict; `mech_records_status` reports counts.
