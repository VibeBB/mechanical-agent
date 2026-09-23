# Operations runbook

## Verification stages

The source of truth is `scripts/verify_all.py` (`--list` dumps the command
table machine-readably).

| Stage | Contents | When |
| --- | --- | --- |
| `docs` | `verify_docs.py` (markdown links + ADR index), `git diff --check` | Markdown-only changes |
| `fast` | `uv sync --locked` (barrier), ruff check, ruff format, pyright, pytest, verify_docs, diff check | Before every PR |

```bash
uv run python scripts/verify_all.py --stage fast
uv run python scripts/verify_all.py --stage docs --jobs 1   # sequential, streamed
```

pytest runs `-n auto --dist loadgroup` by default; `-n 0` for single-test
debugging. Keep collection counts, verdicts, and normalized hashes identical
between parallel and sequential runs.

## Local end-to-end check

```bash
uv sync
uv run python -m mech doctor                          # environment probe
uv run python scripts/e2e_authoring.py \
  --brief examples/enclosure.brief.json --out out/enclosure
uv run python -m mech gates \
  --brief examples/enclosure.brief.json --out out/enclosure   # verify-only rerun
```

`out/` is generated output — never commit it. `python -m mech author` is
idempotent: the same brief produces the same artifacts (sha256 in
`manifest.json`).

## CI

- `ci.yml` — `verify` (matrix 3.12/3.13: sync, ruff, format, pyright,
  pytest, docs) + `plugin-load` (loads `plugins/mech` via
  `openhands-sdk` `Plugin.load` through `scripts/check_plugin_load.py`).
- `workflow-lint.yml` — zizmor on PRs, `.github/**` pushes, merge groups,
  and weekly; uploads SARIF.
- `check-dependency-updates.yml` — weekly + manual; posts candidates to the
  "Dependency update check report" issue.
- `release.yml` — manual dispatch only (see below).

Every `uses:` is pinned to a 40-char SHA with a `# vX.Y.Z` comment;
checkout uses `persist-credentials: false` except the release bump job.

## Releasing

`.github/workflows/release.yml` is `workflow_dispatch` only:

1. `bump-version` runs `scripts/bump_version.py` (`--bump patch|minor|major`
   or `--set X.Y.Z`), updates `plugins/mech/.plugin/plugin.json`,
   `pyproject.toml`, `uv.lock`, commits to main, and refuses if the tag
   already exists. With `version=` equal to current it skips the commit and
   releases current HEAD.
2. `verify` re-runs CI at the bumped SHA.
3. `release` zips `plugins/mech` and creates `vX.Y.Z` with generated notes.

Update `CHANGELOG.md` in the release PR before dispatching.

## Dependency updates

Follow [dependency-updates.md](dependency-updates.md). Weekly candidates
land in the "Dependency update check report" issue. To defer a candidate,
record `{name, reason, deadline}` in
`scripts/dependency_update_deferrals.json` and revisit on the deadline or
when a newer version appears. When adding/removing a dependency or a new
external source, update `scripts/check_dependency_updates.py`, its tests,
and `docs/dependency-updates.md` + this file in the same change.

## Plugin root resolution

Launcher commands (`.mcp.json`, hooks) resolve the plugin root in order:
`$MECH_PLUGIN_ROOT`, `$OPENHANDS_PROJECT_DIR/plugins/mech`,
`$HOME/.agents/plugins/mech`, `$HOME/.openhands/plugins/installed/mech`.
`mech_launcher.py` then points PYTHONPATH at the matching `src/` before
execing `python -m mech.*`, so an installed plugin always runs the sources
it shipped with.

## Failure handling

- `mech doctor` reports `fail` on a missing `build123d`/OCP or exporter —
  check `uv sync` and platform wheels before anything else.
- A gate `unknown` (missing artifact, unreadable STEP, corrupt 3mf) fails
  the design verdict; regenerate with `python -m mech author`, do not
  hand-edit artifacts (the `protect-generated` hook blocks that anyway).
- MCP `isError` results carry `fail_closed: true` + a reason; fix the input
  and retry rather than bypassing the tool.
