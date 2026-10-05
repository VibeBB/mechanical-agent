# Development

## Setup

```bash
uv self update $(grep required-version pyproject.toml | cut -d'"' -f2)
uv sync --locked
```

Python ≥ 3.12 (`requires-python`), uv pinned by `[tool.uv]
required-version`. Run pytest as `env -u BASH_ENV -u "BASH_FUNC_gh%%" uv
run pytest` (the gh shell function breaks stub-gh tests); pytest runs
`-n auto --dist loadgroup` via addopts — use `-n 0` for debugging.

## Verify

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright
uv run python scripts/verify_all.py --stage docs      # markdown only
uv run python scripts/verify_all.py --stage fast      # default before PR
uv run python scripts/verify_all.py --stage standard  # gate/schema changes
```

`verify_all.py --list` dumps the command table; `--group`/`--match`/
`--shard K/N` select subsets. pyright is strict over src+scripts+tests.

## Guard tests (edit code + guard in the same commit)

- `scripts/check_shared_hooks.py` — normalized-AST sha256 of the shared
  hook files; family-canonical, change all copies together.
- `scripts/check_plugin_load.py` — expected agents/skills/commands/hook
  sets; update when `plugins/mech` structure or `hooks.json` changes.
- `tests/test_workflow_guard.py`, `tests/test_launcher*.py`,
  `tests/test_hooks.py`, `tests/test_plugin_assets.py` — grep tests/ for
  any literal before editing workflows, scripts, or the launcher.
- `tests/test_records.py` — asserts `records-policy.json` matches
  `src/mech/records.py` and that `hooks.json` registers the hook.

## Conventions

English everywhere except the README's Japanese half. `encoding="utf-8"`
on all artifact text I/O. Generated artifacts are never edited by hand.
Deterministic gates are the only pass/fail authority — never relax
thresholds to achieve a pass. Negative tests must corrupt the judged
input and confirm failure. Commits are conventional, in English; never
`git add .`, amend, `--no-verify`, force-push, or push to main.

## Layout

See [architecture.md](architecture.md) for the module reference and
[hooks.md](hooks.md) for the hook inventory.
