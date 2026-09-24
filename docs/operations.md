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

## Container images

`docker/mech-tools.Dockerfile` builds the deterministic core image; the
publish workflow also builds `mech-server` (OpenHands agent-server target
`source` on top of the tools image). Both are published to GHCR:

- `ghcr.io/<owner>/mech-tools:<sha>-tools` (immutable) + `:latest`
- `ghcr.io/<owner>/mech-server:<sha>-latest-source` + `:latest`

`docker/image-digests.json` is the digest lock. It is written only by
`publish-mech-images.yml` (main pushes under `docker/`, `src/`,
`plugins/mech/`, `examples/`, `pyproject.toml`/`uv.lock`, or manual
dispatch); the workflow opens a lock-update PR, runs CI on it, and merges.
Do not commit placeholder entries — `scripts/print_locked_image.py` rejects
placeholder digests.

`locked-image-check.yml` (weekly + post-publish) pulls the locked tools
image and re-runs `e2e_authoring` inside the container as the smoke check.

Local build and run instructions live in `docker/README.md`.

## CI

- `ci.yml` — `verify` (matrix 3.12/3.13: sync, ruff, format, pyright,
  pytest, docs) + `plugin-load` (loads `plugins/mech` via
  `openhands-sdk` `Plugin.load` through `scripts/check_plugin_load.py`).
- `workflow-lint.yml` — zizmor on PRs, `.github/**` pushes, merge groups,
  and weekly; uploads SARIF.
- `check-dependency-updates.yml` — weekly + manual; posts candidates to the
  "Dependency update check report" issue.
- `publish-mech-images.yml` — builds and publishes the GHCR images and
  updates the digest lock via a self-merging PR (see "Container images").
- `locked-image-check.yml` — weekly + post-publish smoke of the locked
  image (see "Container images").
- `release.yml` — manual dispatch only (see below).

Every `uses:` is pinned to a 40-char SHA with a `# vX.Y.Z` comment;
checkout uses `persist-credentials: false` except the release bump job and
the image publish job (the lock-update PR needs push credentials).

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
land in the "Dependency update check report" issue as per-surface markdown
tables (pypi, pypi-lock, uv-pin, python-version, github-actions, pypi-uvx,
docker-arg, docker-base). To defer a candidate, record
`{surface, name, latest, review_by, reason}` in
`scripts/dependency_update_deferrals.json` and revisit on the deadline or
when a newer version appears. When adding/removing a dependency or a new
external source, update `scripts/check_dependency_updates.py`, its tests,
and `docs/dependency-updates.md` + this file in the same change.

## Plugin root resolution

Launcher commands (`.mcp.json`, hooks) resolve the plugin root in order:
`$MECH_PLUGIN_ROOT`, `$OPENHANDS_PROJECT_DIR/plugins/mech`,
`$HOME/.agents/plugins/mech`, `$HOME/.openhands/plugins/installed/mech`.
`mech_launcher.py` then execs `python -m mech.*` inside the pinned
`mech-tools` image (resolved via `$MECH_TOOLS_IMAGE` ->
`docker/image-digests.json` -> a local build of the cached Dockerfile),
mounting the matching `src/` read-only at `/plugin-src` and the workspace
at its own path — host Python only launches docker. Any argument other
than `mcp_server`/`prewarm` is forwarded to `mech.cli`, so CLI docs write
`python3 <launcher> <args>`.

## Intake attachments and evidence binding

User-attached images are materialized to `<workspace>/intake/attachments/`
by the `intake-attachments` hook (session_start, user_prompt_submit, stop;
ADR-0004). The hook scans the agent-canvas event store
`~/.openhands/agent-canvas/dev_conversations/<session_id>/events/` —
override with `$MECH_AGENT_EVENTS_DIR` — decodes each `data:` image to
`<sha256[:12]>.<ext>`, and appends provenance to `manifest.jsonl`; the
output dir is overridable via `$MECH_INTAKE_ATTACHMENTS_DIR`. When the
events directory is unreachable (remote runtimes) the hook exits quietly
and the fallback is dropping files into `intake/` manually. `Assumption`
and `OpenQuestion` records may bind such a file with an `evidence` field
(`kind`, `path`, `sha256`, `note`); `check_intake` verifies existence and
hash — fail-closed, same as the `brief_sha256` binding.

## Failure handling

- `mech doctor` reports `fail` on a missing `build123d`/OCP or exporter —
  check `uv sync` and platform wheels before anything else.
- A gate `unknown` (missing artifact, unreadable STEP, corrupt 3mf) fails
  the design verdict; regenerate with `python -m mech author`, do not
  hand-edit artifacts (the `protect-generated` hook blocks that anyway).
- MCP `isError` results carry `fail_closed: true` + a reason; fix the input
  and retry rather than bypassing the tool.
