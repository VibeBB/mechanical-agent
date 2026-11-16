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
`python -m mech review-record` CLI writes the advisory record only; the
VRP v2 vision review (facets, claims, reviewer role) is recorded separately
with `mech_record_vision_review`.

## Enforcement

`require_records.py session-start` marks the session; `require_records.py
stop` (first stop hook) denies finishing while this session owes a
decision, a fresh stage impression for changed artifacts (recorded sha256
must equal current bytes), or a vision review for every vision event /
viewed image — bounded by `max_stop_denials`. `records-status.json`
records the last verdict; `mech_records_status` reports counts.

## VRP v2 logs

`observations/mech/` holds `decisions.jsonl`, `impressions.jsonl`,
`vision-reviews.jsonl`, `reconciles.jsonl`, `insights.jsonl`, `reads.jsonl`
and `song-receipts.jsonl`. Every line carries `schema_version` 2, `sequence`,
`prev_event_id`, `writer` and `event_id` (the SHA-256 of the canonical
record). The writer verifies the chain before appending and refuses a log
that was edited, truncated or reordered; readers report such a log under
`integrity_problems` and never resolve references into it. A log written
entirely by VRP v1 is renamed to `<name>.v1.jsonl` on the first v2 write.

Impressions carry facets (`observed`, `works`, `concerns`, maker/user
`feelings`, `next_actions`), two or more claims quoting exact tokens from the
bound artifacts, and a confidence; a near copy of an earlier impression, or
a concern a sister already disputed, is refused. Taking in a sister artifact
(a circuit board geometry, a UX CMF contract, a simulation response) needs a
`mech_record_read` receipt and an `upstream` entry.

## Blind review

`*.views.png` views sheets and `*.section-*.png` cross-sections are
dual-review images (`dual_review_globs` in `records-policy.json`). After the
primary review, `mech-blind-review` reviews the same image without seeing it
(`reviewer: "blind"`), and the caller records `mech_record_reconcile` over
`[primary, blind]`. A split goes to one tiebreak round
(`[primary, blind, tiebreak]`); a split after the tiebreak stays `unknown`
and never becomes pass. DXF sheet renders keep a single review.

## Insights, songs, digest

`mech_record_insight` moves an insight through
tried/adopted/rejected/deferred/superseded. mech only receives bard songs:
`mech_record_song_receipt` records one receipt per
`liaison/<id>.bard-song.json` (sha256-pinned, never a gate input, never a
request for another song; the song file is protected from edits).
`mech_records_digest` and `mech_records_search` read every plugin's
impressions in the workspace.

## Session-scoped Stop status

The Stop hook excludes a record with an explicit different session ID,
even when its timestamp is recent. Legacy records without an ID are
eligible only from the session start through the following 24 hours;
their use is reported as an attribution warning. Missing session
identity or a missing start marker also leaves attribution unverified.
Reviews bind both the resolved image path and its SHA-256; an event ID
cannot substitute for that binding. Supply an explicit `image_path` to
the review writer so it records the current bytes. Legacy reference-only
reviews remain readable but do not discharge image-review obligations.

Stop writes `observations/<plugin>/records-status.json` and a
`observations/<plugin>/.sessions/<session>.status.json` snapshot:

| Field | Meaning |
| --- | --- |
| `stop_permission` | `deny` while the configured refusal budget remains, then `allow` |
| `record_compliance` | `fail` for missing evidence, `unknown` for attribution warnings, otherwise `pass` |
| `run_completion` | `unknown`; only the execution workflow can establish completion |
| `acceptance` | `unknown`; only the product acceptance workflow can establish it |
| `checkpoint` | Session marker containing the start time and refusal count |

An exhausted refusal budget permits termination while preserving the
unresolved problems. The compatibility `verdict` describes the hook's
problem list only; consumers must use the explicit fields above and must
not infer product acceptance from Stop permission or the absence of
record problems. Reviewer identity propagation and derived-image
ownership require a separate recording contract; this status does not
claim to verify them.

## Session attribution

Pass the native `session_id` from the SessionStart record context in record-tool
inputs. The writer also accepts `OPENHANDS_SESSION_ID` when supplied by the SDK
process; conflicting explicit and environment identities are rejected. The ID is
included in the record hash. Writers never infer it from shared marker files.

Delegated SessionStart hooks expose only native record context (`record-context`), without
recalling earlier review prose. Ordinary plugin SessionStart retains sister-concern recall.

Delegate independent reviews with an opaque `primary_event_id`, the resolved image
path and SHA-256; never send the earlier findings. Reviewers keep their own native
`session_id`. The writer and Stop resolve that reference into an intact primary
with the same plugin, path and hash and a different native session. Every review
role has its own session. Reconciliation belongs to the primary's session.

A copied image has its own round. Historical inputs without identity remain
supported, with bounded timestamp attribution and an unknown compliance warning
at Stop; they cannot satisfy explicitly scoped writer rounds.

Stop permission, record compliance, run completion and acceptance are separate
status fields. Reaching the refusal budget permits stopping while preserving gaps;
it does not establish execution completion or product acceptance.

### Coordinating a delegated primary

When delegating the primary visual review, pass your native `session_id` as
`coordinator_session_id` in the task prompt. The delegate records its own
`session_id` and that coordinator on the primary, then returns the opaque
`primary_event_id` and image path/SHA. The blind reviewer receives only these
references and its own native record context. Do not copy the primary's prose
into the blind review prompt.

The primary author or its declared coordinator can reconcile the bound reviews.
The coordinator's Stop hook retains the independent-review and reconciliation
obligations; the primary delegate reports the handoff without starting another
review loop. A primary started through delegated `record-context` must name its
coordinator. Primary-capable delegates also declare their own Stop hook, so a
legacy primary without coordination cannot silently lose its review debt.
The blind/tiebreak delegate returns one bound review to its caller and has no
workspace-wide Stop hook: it cannot read songs or earlier records to clear those
obligations. The caller still requires its bound independent review and reconcile.
An uncoordinated record from another native session remains outside this run.

These checks concern record attribution and review bookkeeping. SDK startup,
plugin loading, and deterministic tests do not establish LLM judgment quality,
GUI operation, released-image compatibility, or product acceptance.

For an image regenerated at the same path, pass the original native image
observation's `source_event_id` with `image_path` and your own `session_id`.
The typed writer retains the delivered SHA only when that receipt's integrity,
path, and native session match. A foreign or altered receipt cannot supply a
historical revision. Without a matching receipt, the writer hashes the current
file. Delivery evidence remains advisory and does not prove native vision
selection, perception, or product acceptance.
