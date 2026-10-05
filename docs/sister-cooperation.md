# Sister cooperation

mech is one of eleven VibeBB plugins (UX-creator, bard, dashboard,
document, electrical-circuit, firmware, fpga, mechanical,
production-engineering, simulation, wire — https://vibebb.org/). All
cooperation happens through workspace JSON files and `task` delegation;
there are no imports between repos.

## Sister Liaison Protocol (SLP v2) — UX-creator directs

UX-creator writes `liaison/<id>.ux-request.json`; the target sister
answers `liaison/<id>.ux-response.json` beside it. mech's local strict
mirrors (`extra="forbid"`, no UX imports) live in `src/mech/liaison.py`
as `UXRequestV2` / `UXResponseV2` / `RespondPayload`.

### Request v2

`schema_version: 2`, `system: "ux-creator"`, `id` (slug == file stem),
`target_agent` (one of bard, circuit, dashboard, doc, firmware, fpga,
mech, prodeng, sim, wire), `stage`
(requirements|design|manufacturing_handoff|build|evaluation|revision),
`risk` (low|high — high must cite a UX job id in `rationale`), `purpose`
(≥ 20 chars), `rationale`, `requested_changes[]` (≥ 1), `inputs[]`
(`{path, sha256}`), `expected_deliverables[]` (≥ 1), `acceptance[]` (≥ 1),
`depends_on[]` (request ids), `created_at` (ISO-8601 with tz).

### `mech_ux_inbox` / `ux inbox`

For every request targeting mech: `{id, path, stage, risk, state,
reasons, depends_on}` with state precedence `stale` > `answered` >
`blocked` > `new`:

- `stale` — an input is missing or its current sha256 differs from the
  request, or the existing response's `input_hashes` no longer match the
  current input bytes;
- `answered` — a valid response by responder `mech` exists;
- `blocked` — a `depends_on` id has no valid response file (any
  responder) or the request sits on a dependency cycle among visible
  requests;
- `new` — otherwise.

`malformed[]` collects unparseable/invalid files, `id != file stem`
mismatches, and malformed responses for mech requests (treated as not
answered). Valid requests for other targets are skipped silently.

### `mech_ux_respond` / `ux respond --json <file>`

Payload: `{request, status, reason, artifacts[], gate_verdicts[],
design_reports[], decision_refs[], impression_refs[],
questions_for_user[]}`. The writer re-validates the request (must target
mech), hashes current inputs into `input_hashes`, hashes each artifact
(file sha256, or `tree_sha256` for a directory, workspace-confined),
derives `<design>/verdict` plus one `<design>/<check id>` entry per
non-pass check from each `design_reports` file, sets `responded_at`
(tz-aware UTC), and writes `liaison/<id>.ux-response.json`
(deterministic, overwrite allowed).

Refusals (`ValueError` → CLI verdict fail / MCP isError):

- `done` with any fail/unknown gate verdict — answer `needs_info` or
  `rejected` with a reason instead;
- `done` with zero gate verdicts or zero artifacts;
- `done` while the request is stale;
- `done` without ≥ 1 `decision_ref` (must be an `event_id` in
  `decisions.jsonl`) and ≥ 1 `impression_ref` (in `impressions.jsonl` or
  `vision-reviews.jsonl`);
- `reason` < 20 chars unless status is `accepted`/`in_progress`.

`report_ux_inbox.py` (session_start hook) prints pending mech requests
as additional context; `*.ux-response.json` is protected by
`protect-generated` (written only via `mech_ux_respond`).

## Envelope → wire

`export-envelope` / `mech_export_envelope` emits `<name>.envelope.json`
in wire-agent's strict `EnvelopeSource` schema (`schema_version: 1`,
`system: "mech"`, `anchors[] {name, kind, position_mm?}`) from the
brief's `harness_anchors` — unchanged, because wire validates with
`extra="forbid"`. Provenance goes in a sidecar
`<name>.envelope.provenance.json`: `{schema_version: 1, system: "mech",
envelope_sha256, brief_path, brief_sha256, design_report_sha256? (when a
design-report.json is given or found beside the envelope),
decision_refs? (validated against decisions.jsonl)}`; the tool returns
`envelope_sha256`.

## Other interchange

Artifacts (STEP/STL/3MF/DXF + `design-report.json`) feed sim and
production-engineering; briefs and intake feed document. Vision reviews
and decisions are readable by any sister through `observations/mech/`.
