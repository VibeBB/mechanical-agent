# ADR-0002: Fail-closed deterministic gates; LLM/conversation stay L2

- Status: Accepted
- Date: 2026-09-23

## Context

An agent that designs mechanical parts must never let generated geometry
pass on a model's say-so. The family invariant is: input files are truth;
projections never flow back; pass/fail comes only from deterministic
gates; anything unexecuted or unmeasurable is fail-closed.

## Decision

Three layers with a hard boundary:

- **L1 authority**: `src/mech` only. `run_gates` returns `GateCheck[]`
  `{id, subject, status, measured, limit, detail}`; a design verdict is
  `pass` iff every check is `pass`. `unknown` and `fail` both fail.
- **L2 steering**: skills, task sub-agents (`mech-brief`, `mech-design`,
  `mech-review`), commands, MCP tools, vision observations. They may read
  gate output, propose briefs, point at failures, and stop the work —
  they cannot mark anything passed, edit artifacts, or relax a limit.
- **L3 telemetry**: hook logs, vision event records, conversation stats.
  Observe only.

Rules that enforce the boundary:

1. The CLI and MCP tools are thin wrappers over `run_gates`; there is no
   "agent verdict" channel.
2. Generated artifacts are write-protected by the `protect-generated`
   pre_tool_use hook (`.step/.stl/.3mf/.dxf`, `manifest.json`,
   `provenance.json`, `design-report.json`); regeneration via
   `mech_author`/`python -m mech author` only.
3. Intake binds provenance: `part_sources`/`feature_sources` map every
   generated element to R*/A*/Q* ids, and `check_intake` fails a brief
   whose `brief_sha256` no longer matches (post-intake mutation =
   re-intake).
4. Every measurement is wrapped — exceptions become `unknown`, not
   exceptions-up-the-stack; `unknown` fails the verdict.
5. Negative tests corrupt judged inputs (truncated STEP, garbage 3mf,
   mismatched intake hash) and assert fail.

## Consequences

- Reviewers and vision can only stop: an L2 "looks wrong" observation can
  block a design, never push it through a failing gate.
- Thresholds live in `src/mech/standards.py` (PROCESS_LIMITS, MATERIALS);
  changing them is a code change with tests, not a prompt change.
- `--jobs`/parallelism may never affect artifacts, hashes, or verdicts.
