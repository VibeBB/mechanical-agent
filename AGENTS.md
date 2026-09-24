# Agent Working Agreement

> Target: OpenHands Software Agent SDK v1.49.5, Python 3.12+

This document is the working agreement for implementation, verification, and
documentation in this repository. The README is the product overview,
`docs/` holds the specifications and operational policy, `docs/adr/` holds
the design decisions, and the Pydantic models in `src/mech/brief.py` and
`src/mech/intake.py` are the contract source of truth.

README, docs, issues, PRs, code comments, identifiers, and commit messages
are written in English. The README keeps a Japanese section at the end.

## Layout

```text
src/mech/                 # deterministic mechanical-design core
├── brief.py              # design brief schema (the truth source)
├── intake.py             # intake/provenance schema + coverage check
├── standards.py          # materials, process limits, threads, bearings
├── fits.py               # ISO 286 limits-and-fits
├── stackup.py            # 1-D tolerance stackups
├── dfm.py                # process rule checks
├── mechanism.py          # gear/snap/rib/boss/hinge/detent rules
├── generators/           # parametric part generators (lazy build123d)
├── gates.py              # authoritative gate runner
├── export.py             # STEP/STL/3MF/DXF + manifest/provenance
├── dxf_annotate.py       # DXF frame/dims/title block (deterministic overlay)
├── dxf_lint.py           # advisory DXF readability lint (never a verdict)
├── report.py             # design-report.json/md
├── doctor.py             # environment probe
├── mcp_server.py         # stdio MCP boundary
└── cli.py                # python -m mech {doctor,intake,author,gates,export,dxf-lint}
plugins/mech/             # OpenHands plugin
├── skills/               # mech-brief, mech-brief-rules, mech-enclosure,
│                         # mech-mechanism,
│                         # mech-dfm, mech-gates, mech-workflow
├── agents/               # mech-brief, mech-design, mech-review (task sub-agents)
├── commands/             # /mech:design, /mech:doctor, /mech:gates, /mech:export
├── hooks/                # session_start doctor + intake-attachments,
│                         # user_prompt_submit attachments, pre_tool_use artifact
│                         # guard, stop status + attachments, post_tool_use vision
├── scripts/mech_launcher.py
├── .mcp.json
└── .plugin/plugin.json
tests/
scripts/
docker/                 # mech-tools.Dockerfile + image digest lock
examples/               # brief JSON used by docs and the image smoke check
docs/adr/  docs/research/
```

## Invariants

- The design brief and intake files are the source of truth; generated
  artifacts (STEP/STL/3MF/DXF, manifest, provenance, design report) are
  projections and are never edited by hand — the `protect-generated` hook
  blocks such writes.
- Pass/fail verdicts are produced only by the deterministic gates in
  `src/mech/gates.py` and the schemas they serialize.
- LLM output, conversation text, review comments, and vision observations
  are L2 steering aids and are never promoted to a verdict; they may only
  push toward stopping, never toward passing.
- Missing tools, parse failures, unexecuted gates, and unknown states are
  fail-closed: a gate that did not run or could not measure reports
  `unknown`, which fails the design verdict.
- Do not relax thresholds, expected values, or gate rules to achieve a pass.
- Always specify `encoding="utf-8"` when reading or writing artifacts and
  reports as text.
- Never import-bind GPL/AGPL/LGPL code. Copyleft CAD/analysis tools
  (FreeCAD, OpenSCAD, CalculiX, gmsh) may only ever run as unmodified
  subprocesses behind an adapter, per ADR-0001.
- Never write API keys, tokens, or secrets to logs, inputs, or commits.
- Provide negative tests that deliberately corrupt the judged input and
  confirm the corrupted input fails (see `tests/test_gates.py`).

## Plugin boundary

- Do not build custom tool, event, history, task, or executor
  infrastructure; delegate to the OpenHands SDK.
- Invoke sub-agents only with `task` (`TaskToolSet`); mech agents declare
  their required hooks per AgentDefinition because plugin hooks do not
  propagate to sub-agents.
- AgentDefinitions do not declare `skills:`; SKILL.md paths are referenced
  from prompts.
- Skills use `triggers:` (`KeywordTrigger`). A `paths:` glob list makes
  a skill a path-triggered rule instead (deterministic injection when a
  matching file is touched); the two mechanisms are exclusive — keyword
  skills stay model-invocable, rules live in their own `skills/` entries.
- The `mech` MCP server exposes only deterministic entry points (the same
  functions `python -m mech` uses). It contains no agent logic.

## Parallel execution

- Accept parallelism through explicit `--jobs`-style arguments; default
  `min(os.cpu_count() or 1, N)`.
- `ThreadPoolExecutor` for I/O and subprocess waits, `ProcessPoolExecutor`
  for native compute (OCP geometry is process-bound; fork inheritance of
  native handles is unsafe — use spawn workers).
- The parallelism degree must not change artifacts, hashes, or verdicts.
  Pin sequential == parallel with a regression test when a parallel path is
  added.

## Dependencies

PyPI dependencies are pinned in `pyproject.toml` and `uv.lock`. When adding,
removing, or moving a dependency, adding a version ARG or FROM image to
`docker/mech-tools.Dockerfile`, or starting to use a new external source
(other than PyPI), update in the same change: the checker logic in
`scripts/check_dependency_updates.py` (and its tests) plus
`docs/dependency-updates.md` and `docs/operations.md`, and run
`uv run python scripts/check_dependency_updates.py` locally. The weekly
workflow reports candidates to the "Dependency update check report" issue.
For deferred candidates, record the reason and a re-check deadline in
`scripts/dependency_update_deferrals.json`.

Published image digests live in `docker/image-digests.json`, written only
by `publish-mech-images.yml`; do not commit placeholder entries.

## Verification

```bash
uv sync
uv run python scripts/verify_all.py --stage docs   # markdown-only changes
uv run python scripts/verify_all.py --stage fast   # default before PR
```

`verify_all.py` runs barrier-marked commands alone and consecutive
non-barrier commands in parallel up to `--jobs` workers; `--list` dumps the
machine-readable command table. pytest runs `-n auto --dist loadgroup`; use
`uv run pytest -n 0` for single-test debugging.

## Git

Write commit messages in English. Do not use `git add .`, amend commits,
`--no-verify`, force push, direct pushes to main, `reset --hard`,
`clean -fd`, `checkout -- file`, or `stash drop`. Do not commit generated
`out/` files, secrets, or environment files. Split dependent changes into
bottom-up stacked PRs; independent changes go on separate PRs based on main.
