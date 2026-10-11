# ADR-0010: VRP v2 records and blind render review

Status: Accepted
Date: 2026-10-11

## Context

VRP v1 (ADR-0007) let a model append free prose that nobody had to answer:
logs could be edited or truncated unnoticed, the same concern could be raised
forever, a rejected idea could come back unchanged, and one vision review of a
views sheet or cross-section was taken as seen. wire-agent shipped VRP v2 as the
family reference; the user chose to port all of it to every plugin.

## Decision

- Copy the canonical v2 hooks (`_records.py`, `require_records.py`,
  `blind_guard.py`) byte-for-byte from wire-agent, and mirror `_records.py`
  as `src/mech/_vrp.py`. Ruff formatting and linting skip these files;
  `scripts/check_shared_hooks.py` pins the digests and
  `tests/test_records.py` pins the mirror to the hook bytes.
- `src/mech/records.py` keeps the typed pydantic writers and `RECORDERS`,
  now delegating validation to `_vrp.py`: hash-chained logs, structured
  grounded impressions, near-duplicate refusal, read receipts, insight
  lifecycle, dispute no-re-raise, reconcile rounds, song receipts, digest and
  search behave exactly as in wire.
- `**/*.views.png` and `**/*.section-*.png` are the dual-review globs: the new
  `mech-blind-review` sub-agent records the blind round behind
  `blind-guard`, and the caller reconciles.
- mech only receives bard songs (`song-receipt`); it never delivers songs,
  and a receipt never asks for another one. `protect-generated` makes
  `liaison/*.bard-song.json` and the new logs append-only.
- The CLI and MCP server gain `reconcile`, `insight`, `song-receipt`, `read`,
  `digest` and `search`.

## Consequences

Records remain advisory: no gate reads them. Existing v1 logs are archived as
`<name>.v1.jsonl` on the first v2 write. Callers that recorded impressions
with the v1 shape now get a validation error naming the missing v2 fields.
The vendored core adds about 1,000 statements to `src/mech`; C2
(63.21%) and MC/DC (35.73%) fell below their floors, so those two moved one
point below the measured values (`docs/test-coverage.md`).
