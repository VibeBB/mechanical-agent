# Operations runbook

## SBOM attestations

`publish-mech-images.yml` generates and attests a package-level SPDX-2.3 SBOM
for the published tools digest and uploads the full Syft SBOM as a 90-day
workflow-run artifact. The lock records the returned `sbom_attestation` URL;
`locked-image-check.yml` verifies it when
present and warns while continuing when absent.
The attested SBOM omits file entries and relationships involving files to
stay below the 16 MiB limit.

## Verification stages

The source of truth is `scripts/verify_all.py` (`--list` dumps the command
table machine-readably).

| Stage | Contents | When |
| --- | --- | --- |
| `docs` | `verify_docs.py` (markdown links + ADR index), `git diff --check` | Markdown-only changes |
| `fast` | `uv sync --locked` (barrier), ruff check, ruff format, pyright, pytest with coverage, shared-hook check, verify_docs, diff check | Before every PR |

```bash
uv run python scripts/verify_all.py --stage fast
uv run python scripts/verify_all.py --stage docs --jobs 1   # sequential, streamed
```

The fast stage runs pytest with `--cov --cov-report=term-missing:skip-covered`;
coverage measures `src/mech`, disables branch coverage, and enforces an 83%
minimum. pytest runs `-n auto --dist loadgroup` by default; `-n 0` for
single-test debugging. Keep collection counts, verdicts, and normalized hashes
identical between parallel and sequential runs.

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

Only the immutable per-sha tags are pushed at build time. The `:latest`
tags are promoted with `docker buildx imagetools create` (a server-side
manifest copy, so provenance/SBOM attestations keep referencing the same
digest) only after the Trivy fixable-CVE gates and the tools smoke check
pass — a gate failure leaves the previous good `:latest` untouched.
`workflow_dispatch` is additionally restricted to `refs/heads/main` so a
manual run cannot sign and push images from an arbitrary ref.

The tools image installs `librsvg2-bin` (unpinned Debian 13 apt) for
`mech_render` / `python -m mech render`, which turns an exported `.dxf`
into an `.svg` (ezdxf `SVGBackend`, in-process) plus a `.png`
(`rsvg-convert`, override via `$MECH_RSVG_CONVERT`) so the vision lane can
look at the drawing. `mech_render` also takes `baseline_path`: a missing
baseline JSON records `{image, image_sha256}`, a readable one reports
`match`/`diff`. Renders are advisory projections — the
`protect-generated` hook covers `.svg`/`.png` writes, and review records
follow the shared `review-visual-<slug>.advisory.json` contract
(`src/mech/advisory.py`, ADR-0005).

`docker/image-digests.json` is the digest lock. It is written only by
`publish-mech-images.yml` (main pushes under `docker/`, `src/`,
`plugins/mech/`, `examples/`, `pyproject.toml`/`uv.lock`, changes to the
publish workflow or lock scripts, or manual dispatch); the workflow opens a
  lock-update PR, dispatches and waits for `ci.yml` and
  `workflow-lint.yml` on the bot branch, and merges.
Do not commit placeholder entries — `scripts/print_locked_image.py` rejects
placeholder digests. The same `mech_tools` entry ships inside the plugin at
`plugins/mech/skills/mech-workflow/tools-image.json` (rewritten by the same
workflow) so an installed plugin resolves the pinned tools image without the
extension cache — `mech_launcher.py` checks `<plugin>/tools-image.json`,
then `<plugin>/skills/*/tools-image.json`, then
`docker/image-digests.json`.

The `mech_tools` image build publishes a GitHub build-provenance attestation;
its URL is stored alongside the digest in both tools lock files. The locked
image check verifies available provenance against
`.github/workflows/publish-mech-images.yml`. Older pins without an attestation
emit a warning and continue. The `mech_server` digest is separate and is not
covered by this tools-image provenance check (ADR-0006).

The tools container runs as the host uid, whose home does not exist inside
the image: the launcher pins `HOME`/`TMPDIR`/`XDG_*` to `/tmp` instead of
forwarding the host values so fontconfig, ezdxf and other cache-writing
tools work. Source/image resolution still consults both `$HOME` and the
account's real home for `~/.openhands/cache/extensions/mechanical-agent-*`,
so a `HOME` override applied to the container does not blind the launcher.
In `--warn` doctor mode (the SessionStart hook) the launcher reports a
missing local image instead of pulling it.

`locked-image-check.yml` (weekly + post-publish) pulls the locked tools
image through `mech_launcher.py`, runs `doctor` and the shipped
`e2e_authoring` example, and verifies available provenance and SBOM
attestations. Smoke output is mounted into runner temp and uploaded as an
artifact even if the smoke step fails.

Local build and run instructions live in `docker/README.md`.

## CI

- `ci.yml` — `verify` (matrix 3.12/3.13: sync, ruff, format, pyright,
  pytest, docs) + `dockerfile-lint` (hadolint + BuildKit `--check` on
  `docker/mech-tools.Dockerfile`) + `plugin-load` (loads `plugins/mech` via
  `openhands-sdk` `Plugin.load` through `scripts/check_plugin_load.py`).
- `workflow-lint.yml` — actionlint and zizmor on PRs, `.github/**` pushes,
  manual dispatch, and weekly; uploads SARIF.
- `check-dependency-updates.yml` — weekly + manual; writes its report under
  runner temp, appends the run URL to the report and step summary, and posts
  candidates to the "Dependency update check report" issue. Fetch failures
  are reported as unknown and keep the issue open.
- `digest-lock-sweep.yml` — periodically retries merging eligible digest-lock
  PRs while required checks remain enforced; after a sweep merge it
  dispatches `ci.yml` and `locked-image-check.yml` on main (a token merge
  does not fire push-triggered workflows).
- `publish-mech-images.yml` — builds and publishes the GHCR images, attests
  the tools image, and updates the digest lock via a self-merging PR (see
  "Container images").
- `locked-image-check.yml` — weekly + post-publish smoke of the locked
  image (see "Container images").
- `container-audit.yml` — weekly Trivy re-scan of the locked tools image
  plus Docker CIS and informational Lynis reports; maintains the
  "Container hardening report" issue (see "Container hardening").
- `main-ci-failure-issue.yml` — watches completed main runs from CI,
  the container hardening audit, dependency updates, digest sweeps,
  locked-image checks, PR cleanup, publishing, releases, scorecard, and
  workflow lint; maintains a tracking issue. Concurrency keys on the
  triggering run id so queued reports are not evicted.
- `pr-branch-cleanup.yml` — removes merged PR branches.
- `release.yml` — manual dispatch only (see below).

Every `uses:` is pinned to a 40-char SHA with a `# vX.Y.Z` comment;
checkout uses `persist-credentials: false` except the release bump job and
the image publish job (the lock-update PR needs push credentials).

## Releasing

`.github/workflows/release.yml` is `workflow_dispatch` only:

1. `bump-version` runs `scripts/bump_version.py` (`--bump patch|minor|major`
   or `--set X.Y.Z`), updates `plugins/mech/.plugin/plugin.json`,
   `pyproject.toml`, `plugins/mech/skills/*/SKILL.md`, `uv.lock`, commits to
   main, and refuses if the tag
   already exists. With `version=` equal to current it skips the commit and
   releases current HEAD.
2. `verify` re-runs CI at the bumped SHA.
3. `release` zips `plugins/mech` and creates `vX.Y.Z` with generated notes.

Update `CHANGELOG.md` in the release PR before dispatching.

`dry_run: true` rehearses the flow: `bump-version` validates the version
arithmetic and tag availability against HEAD without committing, pushing,
or opening the bump PR; `verify`, `install-smoke`, and the zip build run
on that SHA; the tag and `gh release create` steps are skipped. Use it to
exercise the pipeline before the first real release — the version-bump
fallback-PR path is the one piece a dry run still cannot reach (it ends in
a merge to main).

## Dependency updates

Follow [dependency-updates.md](dependency-updates.md). Weekly candidates
land in the "Dependency update check report" issue as per-surface markdown
tables (pypi, pypi-lock, uv-pin, python-version, github-actions, pypi-uvx,
docker-arg, docker-base, apt, git-clone). To defer a candidate, record
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
`docker/image-digests.json`; an unresolvable or unpullable ref is an
error — the launcher never falls back to a local build),
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

## OpenHands runtime surfaces

Runtime policy surfaces that the plugin declares but the host executes:

- `permission_mode: never_confirm` on every mech sub-agent. The SDK's
  task path (`openhands-tools` `task/manager.py`, verified 1.49.5 and
  upstream `main`) never attaches a `security_analyzer` to the child
  `LocalConversation`, so `confirm_risky` saw every action as `UNKNOWN`
  and auto-resumed — zero gating plus status churn. `never_confirm`
  declares the real behavior; revisit if the SDK propagates the parent's
  analyzer.
- `model:` resolves through `LLMProfileStore` (`~/.openhands/profiles/`).
  Authoring sub-agents (mech-brief, mech-design) use `vibebb-author`;
  mech-review uses `vibebb-review`. A missing profile raises `ValueError`
  at task spawn, so the `session_start` hook
  `hooks/scripts/ensure_llm_profiles.py` clones the conversation's
  `active_profile` into `vibebb-author.json`/`vibebb-review.json` when
  they are absent — edit those files afterwards to route the authoring
  or review lane at a different model. To fall back to the conversation
  model, set `model: inherit` locally.
- Secrets: `${VAR}` / `${VAR:-default}` in `mcp_config` expands through
  the conversation `SecretRegistry` before env, and the launcher passes
  the process env through to the stdio MCP server — a canvas-registered
  `MECH_*` secret reaches `mech_*` tool code end-to-end. Bash commands
  also receive registry values when the key name appears in the command
  text.
- The `safety-rail` `pre_tool_use` hook (`hooks/scripts/safety_rail.py`)
  denies a deterministic denylist on terminal commands: root/home `rm
  -rf`, block-device writes, power commands, and the git operations the
  working agreement bans. It is advisory depth — not a security
  analyzer — and passes everything it does not positively recognize.
- `.openhands/memory/MEMORY.md` seeds the project-tier persistent
  memory loaded when the host enables `AgentContext(load_memory)`
  (canvas "Settings > Agent Context"). The agent maintains the index;
  keep the seed to durable facts only.
- `StuckDetector` is on by default for every conversation including
  task sub-agents; `max_iteration_per_run` remains the repo-side bound.

## Failure handling

- `mech doctor` reports `fail` on a missing `build123d`/OCP or exporter —
  check `uv sync` and platform wheels before anything else.
- A gate `unknown` (missing artifact, unreadable STEP, corrupt 3mf) fails
  the design verdict; regenerate with `python -m mech author`, do not
  hand-edit artifacts (the `protect-generated` hook blocks that anyway).
- MCP `isError` results carry `fail_closed: true` + a reason; fix the input
  and retry rather than bypassing the tool.

## Launcher-side verification

`MECH_VERIFY_ATTESTATION` accepts `auto` (the default), `require`, or `off`.
Before pulling a lock-provided image, and on every `prewarm`, the launcher
uses `gh attestation verify` with the lock entry and publisher workflow.
`auto` prints one note and skips for an image override, missing attestation,
missing `gh`, or failed `gh auth status`; once verification starts, failure
or timeout prevents the pull. `require` makes skip conditions errors, while
`off` never verifies. Ordinary invocations do not re-verify a locally
present image, and `--warn` doctor paths never verify.

## Container hardening

Three layers were adopted after a comparative evaluation of Lynis,
`docker build --check`, Trivy, Grype, Dockle, and hadolint:

- **Dockerfile lint** (`dockerfile-lint` job in `ci.yml`): hadolint
  v2.15.1 via `hadolint-action` v3.5.0 plus `docker build --check`
  (BuildKit built-in). `.hadolint.yaml` allows only docker.io and
  ghcr.io registries and waives DL3008 (exact deb pins rot when Debian
  archives drop them; downloaded tools are already version+sha256
  pinned).
- **Image scan on publish** (`publish-mech-images.yml`): Trivy v0.75.0
  via `trivy-action` v0.36.0 scans each pushed digest —
  `mech-tools` (skipped under `skip_tools`) and `mech-server` — for
  CRITICAL/HIGH fixable vulnerabilities, secrets, and misconfiguration,
  gated (`exit-code 1`), with SARIF uploaded to code scanning
  (`category: trivy-mech-tools`, `trivy-mech-server`) and a full JSON
  report as an artifact. The action is SHA-pinned and `version:` is
  explicit — the March 2026 Trivy supply-chain compromise made both
  non-negotiable.
- **Weekly audit** (`container-audit.yml`, Mondays 03:47 UTC): pulls the
  pinned `mech_tools` digest from `docker/image-digests.json` (the
  primary image; `mech_server` is the downstream SDK layer built from it
  and is already scanned at publish time), re-scans with a fresh
  vulnerability DB (new CVEs against the frozen image), runs the Docker
  CIS compliance report, runs an informational in-image Lynis 3.1.7
  audit, aggregates `container-hardening.json` (artifact, together with
  `trivy-image.json` and `trivy-cis.json`), and
  edits/creates a "Container hardening report" issue. The issue closes
  automatically when fixable HIGH/CRITICAL findings reach zero. The
  Lynis Hardening Index is recorded as a trend metric only — its
  denominator shifts with container-skipped tests, so it never gates.

Not adopted, with reasons: `lynis audit dockerfile` (~6 greps, frozen
since 2018, subset of hadolint, hardening index always 1);
Dockle (v0.4.15 stale; its CIS-derived checks are covered by Trivy's
`--compliance docker-cis` report); Grype (equivalent for the SBOM path,
kept as fallback); checkov (redundant third linter); `cisofy/lynis`
Docker image (does not exist — Lynis runs from a pinned git clone);
non-root USER enforcement and HEALTHCHECK enforcement (AVD-DS-0002 and
AVD-DS-0026 — expected findings on a batch CLI tools image run via
`docker run --rm` under `mech_launcher.py`'s `--user uid:gid` and
`--cap-drop ALL` runtime flags; documented here rather than waived so the
CIS column stays honest).

Changelog evaluation for the adopted pins is in the introducing PR.
Suppressions: `.hadolint.yaml` waivers above; `.trivyignore` holds
time-boxed finding IDs — entries must carry an `exp:` date and a
rationale line here when added.

The uv-managed CPython's bundled `pip` payload (vendored urllib3,
msgpack, setuptools — never invoked; dependencies install via `uv` and
the shipped venv is pip-less) is stripped in the `uv python install`
layer, so the publish gate stays clean without `.trivyignore` waivers.

The pinned `debian:13-slim` base digest keeps shipping `libpcre2-8-0`
`10.46-1~deb13u2`; the tools Dockerfile upgrades it in-build to the
fixed `deb13u3` (CVE-2026-103111) via `apt-get install --only-upgrade`,
keeping the publish gate green between base-digest bumps without a
waiver. The same fix propagates to `mech-server`, which the SDK build
layers on top of the tools image.

`mech-server` findings (enumerated from a 2026-10-03 scan of
`ghcr.io/vibebb/mech-server@sha256:8129ed13...` — the image had never
been scanned because earlier publishes aborted at the tools gate) are
upstream-borne and waived per-ID in `.trivyignore` with
`exp:2027-01-03`: SDK `.venv` packages (pypdf, urllib3, virtualenv,
wheel, setuptools, msgpack, jaraco.context), nodejs_wheel vendored
node_modules, bundled Go binaries (rootlesskit, docker-buildx), and
upstream Dockerfile copies (DS-0029). They clear on the next
openhands-sdk bump — tracked in `scripts/dependency_update_deferrals.json`.

The weekly audit runs Lynis as container root (`--user 0`) with the
committed `docker/lynis-container.prf` profile, which skips tests that
are inapplicable inside a container (kernel/systemd/mounts/storage/
network/PAM/accounting are governed by the runtime flags below, not the
image fs). The profile raises the measured Hardening Index from ~62 —
63 on the 2026-10-03 audit run; the index drifts as upstream Lynis adds
or drops tests, so treat it as a trend, not a target — and reduces the
suggestion list to image-actionable items;
remaining suggestions are fixed in the Dockerfile (`UMASK 027` in
login.defs, Lynis AUTH-9328) or silenced only with a documented reason.
Because the tightened umask makes Lynis write its report and log 0640
root-owned, the audit step `chmod 644`s both files so the runner-side
grep can read the index.

`mech_launcher.py` applies the runtime-hardening flags the container
profile defers to: `--network none`, `--user uid:gid`,
`--cap-drop ALL`, `--security-opt no-new-privileges`. A `--read-only`
root filesystem stays an optional hardening for callers that supply
tmpfs for tools that need scratch space.

### CIS baseline

The Trivy CIS compliance scan reports `DS-0002` (image runs as root) and
`DS-0026` (no `HEALTHCHECK`) on every tools image. Both are waived with
`exp:` entries in `.trivyignore`: these are CI build/tool containers, not
deployed services — workflows that need a non-root UID already run the
image with `docker run --user`, and batch tooling has no health endpoint
to probe. The waivers renew or get re-fixed by Dockerfile changes when
they lapse.

For `mech-server` the findings are upstream-owned: the image is
assembled by the OpenHands agent-server build in its own repository,
so `USER`/`HEALTHCHECK` changes cannot land here. A `HEALTHCHECK`
against the server's HTTP listener was evaluated and deferred for the
same reason.

## CI runner network auditing

Every job in the repo-owned workflows uses `step-security/harden-runner`
in audit-only mode. It observes network egress without blocking requests;
per-run insights are available in the GitHub Actions job summary. The five
hash-locked family-canonical workflows (`pr-branch-cleanup.yml`,
`dependency-review.yml`, `scorecard.yml`, `workflow-lint.yml`,
`main-ci-failure-issue.yml`) carry it only once the family canon adds it —
shared files must stay byte-identical across the sibling repos.

## Digest-lock PR verification

The publisher dispatches `ci.yml` and `workflow-lint.yml` on the lock branch, then polls the authoritative required-check set for up to 30 minutes. Non-required failures do not block publishing; a concluded required-check failure or a PR closed without merge fails the job. A PR merged externally triggers the existing post-merge main workflows without waiting for their results. If required checks remain pending at the deadline, the publisher arms squash auto-merge with branch deletion and exits successfully so branch protection can complete the merge.

SPDX generation prefers the GHCR registry source, writes temporary data under
the runner's temporary directory, and disables file metadata. The publisher
removes file entries and relationships involving files to produce the
package-level SPDX-2.3 SBOM. A guard reports disk space and the attested SBOM
size after transformation and fails above 16 MiB; the full Syft SBOM is
uploaded as a 90-day workflow-run artifact.

## Settings-level posture (recorded decisions)

The following live in repository Settings rather than code; they are
intentional for the solo-maintainer bot-merge workflow and are recorded
here so audits do not re-flag them:

- Branch protection does not require approving reviews, code owners, or
  "apply to administrators": every merge is performed by automation
  (digest-lock, version-bump, and Devin PRs), so required approvers would
  only add friction to a pipeline that already gates on the required-check
  set. OpenSSF Scorecard reports this as Branch-Protection 3 and
  Code-Review 0; that is the recorded trade-off, not an oversight.
- The Dependency graph must stay enabled for `dependency-review.yml` to
  evaluate pull requests.
- `release.yml` is dispatch-only; run it once with `dry_run=true` before
  the first real release to rehearse bump, verify, and install-smoke
  without creating a GitHub release.
