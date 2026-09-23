# Contributing

Thanks for helping build mech. This repository follows a strict contract —
read [AGENTS.md](AGENTS.md) first; the short version is below.

## Ground rules

- English only: issues, PRs, commits, docs, comments, identifiers
  (README keeps a Japanese appendix).
- Python ≥ 3.12, uv `==0.12.18`, ruff, pyright strict, pytest.
- All pass/fail logic lives in `src/mech` deterministic gates. LLM output,
  reviews, and vision observations never produce verdicts.
- Fail-closed: missing tools, parse failures, unexecuted gates, and
  unknowns fail the design.
- Never import-bind GPL/AGPL/LGPL code (ADR-0001). Never commit secrets.
- `encoding="utf-8"` on every text read/write.

## Setup

```bash
uv sync
uv run python scripts/verify_all.py --stage fast
```

`--stage docs` is enough for Markdown-only changes. CI runs the same
commands on Python 3.12 and 3.13 plus a plugin-load job that loads
`plugins/mech` through `openhands-sdk`.

## Pull requests

- Keep changes minimal and focused; follow surrounding conventions.
- New gates or brief fields need tests — including a negative test that
  corrupts the judged input and proves it fails.
- New dependencies or new external sources must update
  `scripts/check_dependency_updates.py`, its tests, and
  `docs/dependency-updates.md` / `docs/operations.md` in the same change.
- Dependent changes: bottom-up stacked PRs. Independent changes: separate
  PRs on `main`.

## Reporting bugs / requesting features

Open an issue with the design brief (sanitized) or a minimal reproducing
`design.brief.json` when reporting gate or generator bugs. For security
issues use [SECURITY.md](SECURITY.md) instead.
