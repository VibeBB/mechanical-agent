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

## Checked by `scripts/check_dependency_updates.py`

- PyPI dependencies (runtime + dev), resolved against latest PyPI release.
- uv required-version against PyPI `uv`.
- GitHub Actions `uses:` SHA pins against latest repo tag.
- `uvx` tool pins in workflows against PyPI.

The weekly workflow posts the report to the "Dependency update check
report" issue. Deferred candidates are recorded in
`scripts/dependency_update_deferrals.json` with a re-check deadline.

## Procedure

1. Run `uv run python scripts/check_dependency_updates.py` locally.
2. For each candidate, read the upstream release notes: record used APIs,
   defaults, breaking changes, and the adoption decision in this file.
3. Bump the pin in the same change (pyproject/uv.lock via `uv lock`,
   workflow SHA + comment, or `uvx` pin).
4. Run `verify_all.py --stage fast`.
5. If deferring: add `{name, reason, deadline}` to
   `scripts/dependency_update_deferrals.json`.

## Not covered

- OCP/OCCT internals (ride along with the build123d pin).
- Transitive dependencies (uv.lock is the record; bumps ride direct bumps).
