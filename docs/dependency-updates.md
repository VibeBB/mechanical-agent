# Dependency updates

This document records the pinned versions in use, where they come from, and
the adoption decision for each. Update it in the same change that touches
`pyproject.toml`, a workflow pin, or a new external source.

## Runtime dependencies (pyproject.toml + uv.lock)

| Package | Pin | Source | Decision |
| --- | --- | --- | --- |
| build123d | `==0.11.1` | PyPI | Exact pin — CAD kernel behavior is release-sensitive (mesh/boolean edge cases verified against this version). Bundles OCP (OCCT 7.9) and ezdxf. |
| pydantic | `>=2` | PyPI | Floor pin — v2 API only (`model_validate`, `model_dump`). |
| mcp | `>=1.29,<2` | PyPI | stdio server boundary; `<2` caps the breaking major. |
| openhands-sdk | `==1.49.4` | PyPI | Exact pin — plugin API contract. |
| openhands-tools | `==1.49.4` | PyPI | Exact pin — matches SDK. |

## Dev dependencies (dev group)

| Package | Pin | Notes |
| --- | --- | --- |
| packaging | `>=26` | Used by `scripts/check_dependency_updates.py` |
| pyright | `>=1.1.414` | strict mode |
| pytest | `>=9` | suite runner |
| pytest-xdist | `>=3` | `-n auto --dist loadgroup` |
| ruff | `>=0.16` | lint + format |

## Tooling pins

| Tool | Pin | Where |
| --- | --- | --- |
| uv | `==0.12.18` | `[tool.uv] required-version` |
| Python | `>=3.12`, CI matrix 3.12/3.13 | pyproject `requires-python` |
| zizmor | `1.30.1` (uvx pin) | `workflow-lint.yml` |

## GitHub Actions pins

All `uses:` entries are pinned to a 40-char SHA with a `# vX.Y.Z` comment:

| Action | Pinned version |
| --- | --- |
| actions/checkout | v7.0.1 |
| astral-sh/setup-uv | v10.2.0 |
| github/codeql-action/upload-sarif | v4.38.1 |
| docker/setup-buildx-action | v4.4.1 |
| docker/login-action | v4.6.0 |
| docker/build-push-action | v7.4.0 |

## Docker image pins

| Item | Pin | Where |
| --- | --- | --- |
| ubuntu base image | `26.04` | `docker/mech-tools.Dockerfile` `FROM` |
| uv | `0.12.18` | `docker/mech-tools.Dockerfile` `ARG UV_VERSION` (must equal `[tool.uv] required-version`) |
| Python in image | `3.12` | `uv python install` inside the Dockerfile |

## Checked by `scripts/check_dependency_updates.py`

The checker renders a per-surface markdown report (plus optional JSON) with
state columns `update available` / `deferred` / `up to date`. Surfaces:

- `pypi` — runtime + dev dependencies; `current` is the version resolved in
  `uv.lock`, compared against the latest PyPI release (spec floors do not
  count as current).
- `pypi-lock` — transitive `uv.lock` drift from `uv lock --upgrade
  --dry-run` (Update/Add/Remove lines); only drifted entries are listed.
- `uv-pin` — `[tool.uv] required-version` against PyPI `uv`.
- `python-version` — Python minors referenced by `requires-python`, the
  Dockerfile `uv python install`, and the CI matrix, against the latest
  stable CPython minor tag.
- `github-actions` — `uses:` SHA pins against the latest repo tag (the
  `# vX.Y.Z` comment is the recorded current version).
- `pypi-uvx` — `uvx tool@version` pins in workflows against PyPI.
- `docker-arg` — Dockerfile `ARG UV_VERSION` against the latest
  `astral-sh/uv` tag; the ARG is asserted equal to `[tool.uv]
  required-version` by a unit test.
- `docker-base` — `FROM ubuntu:YY.MM` against the newest Ubuntu `YY.04`
  LTS tag on Docker Hub.

The weekly workflow posts the markdown report to the "Dependency update
check report" issue. Deferred candidates are recorded in
`scripts/dependency_update_deferrals.json` as
`{surface, name, latest, review_by, reason}`; `name` may be `"*"` to cover
a whole surface entry (e.g. every Python-version row). A deferral applies
only while `review_by` has not passed and still matches the reported
`latest`, so expired or superseded deferrals re-list automatically.

## Procedure

1. Run `uv run python scripts/check_dependency_updates.py` locally.
2. For each candidate, read the upstream release notes: record used APIs,
   defaults, breaking changes, and the adoption decision in this file.
3. Bump the pin in the same change (pyproject/uv.lock via `uv lock`,
   workflow SHA + comment, or `uvx` pin).
4. Run `verify_all.py --stage fast`.
5. If deferring: add `{surface, name, latest, review_by, reason}` to
   `scripts/dependency_update_deferrals.json`.

## Current deferrals

| Surface | Name | Latest | Re-check | Reason |
| --- | --- | --- | --- | --- |
| pypi | build123d | 0.13.0 | 2027-01-01 | `threejs-materials>=1.2.1` (required by build123d 0.13.0) pins `pillow>=12.2.0,<12.3.0`, conflicting with `openhands-sdk==1.49.4` requiring `pillow>=12.3.0`. Unsatisfiable until the SDK loosens the pillow bound. |
| pypi | mcp | 2.2.0 | 2027-01-01 | `openhands-sdk` -> `fastmcp-slim` requires `mcp>=1.24.0,<2.0`; mcp 2.x cannot coexist with the SDK pin. |
| python-version | * | 3.14 | 2027-04-01 | Matrix is 3.12/3.13; SDK support and build123d/OCP wheels for 3.14 unconfirmed. |

## Not covered

- OCP/OCCT internals (ride along with the build123d pin).
- Transitive dependencies stay pinned in `uv.lock`; the `pypi-lock`
  surface reports drift but bumps still ride direct spec changes
  (`uv lock --upgrade` when applied).
