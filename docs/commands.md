# Commands

## Plugin commands (`/mech:*`)

`plugins/mech/commands/` — each is a prompt file with `allowed-tools`.

| Command | Args | Does |
|---|---|---|
| `/mech:design` | `<project_dir> <requirements summary>` | clarifies requirements, plans with task-tracker, delegates mech-brief → mech-design → mech-review |
| `/mech:doctor` | — | runs `mech_launcher.py doctor` and reports the JSON verdict |
| `/mech:gates` | `<brief.json> <out_dir>` | re-runs all deterministic gates on an existing output dir |
| `/mech:export` | `<brief.json> <out_dir>` | regenerates artifacts only |

Inside OpenHands all commands go through `scripts/mech_launcher.py`
inside the pinned `mech-tools` image; in a repo checkout
`uv run python -m mech <args>` is equivalent.

## CLI (`python -m mech`, `src/mech/cli.py`)

Every subcommand prints a JSON verdict to stdout; `verdict` `pass`/`ready`
exits 0, anything else exits 1 (fail-closed — exceptions become
`{verdict: fail, stage, detail}`).

| Subcommand | Args | Does |
|---|---|---|
| `doctor` | `--warn` | probes build123d/OCP, ezdxf, lib3mf, rsvg-convert; `--warn` always exits 0 |
| `intake` | `--brief --intake` | `check_intake` coverage verdict |
| `author` | `--brief --out` | generate + export + gates + design-report |
| `export` | `--brief --out` | generate + export only |
| `gates` | `--brief --out` | regenerate + gates against an out dir |
| `dxf-lint` | `--in <dxf> [--out]` | advisory readability lint |
| `render` | `--dxf [--out] [--dpi] [--baseline]` | DXF→SVG→PNG + optional sha256 baseline |
| `render-views` | `--step [--baseline]` | STEP→`.views.svg`/`.views.png` 2x2 sheet |
| `board-import` | `--geometry <circuit *.board-geometry.json> [--source-path]` | prints the enclosure `board` block (size, thickness, keepout = tallest top part, `MH<n>` holes, `source` hash pin) plus `connector_openings` targets; `fail` on an incomplete geometry |
| `sim-request` | `--brief <brief.json> --out-dir <dir> [--workspace <root>]` | writes `<name>.ruggedness.sim.json` (simulation `ruggedness` section) and `<name>.ruggedness.sim-request.json` (v1, `kind: ruggedness`); `fail` without `enclosure.ruggedness` or, for vibration, without `enclosure.board` |
| `appearance` | `--brief <brief.json> --out-dir <dir>` | writes `<name>.mech-appearance.json` (cosmetic class per face, defect limits, viewing condition, accept/reject limit samples) for production-engineering; `fail` without `appearance` |
| `export-envelope` | `--brief --out [--design-report] [--decision-ref]*` | writes `*.envelope.json` + `*.envelope.provenance.json`; returns `envelope_sha256` |
| `review-record` | `--image --model --checklist dxf_outline|part_render|assembly_render|intake_image --findings <json> [--impression|--impression-file] [--summary] [--out]` | writes `review-visual-<slug>.advisory.json` and mirrors it into `vision-reviews.jsonl` (`vision_log` in output) |
| `record` | `decision|impression|vision-review|status --json <file>` | appends a VRP record (`--json` required except for `status`, which prints counts + last stop verdict) |
| `ux` | `inbox` / `respond --json <file>` | liaison inbox listing / response write (SLP v2) |
