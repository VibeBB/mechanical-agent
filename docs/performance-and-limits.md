# Performance and limits

## Measured wall times

Example enclosure (`examples/enclosure.brief.json`, 80×60×30 mm shell +
lid + board keepout), measured 2026-10-05 on the dev box (Python 3.14,
build123d 0.13.0, rsvg-convert installed):

| Operation | Wall time |
|---|---|
| `render_views` on `demo.step` (assembly) | 0.54 s |
| `render_views` on `demo-shell.step` | 0.47 s |
| `render_views` on `demo-lid.step` | 0.13 s |
| `render_views` on `demo-board_keepout.step` | 0.06 s |
| `render_dxf` on `demo-shell.dxf` | 0.07 s |
| `render_dxf` on `demo-lid.dxf` | 0.13 s |

Generated PNGs live outside the repo (scratch dir): the views sheets add
≈ 0.5 s per STEP for this size of assembly; the cost is dominated by
`project_to_viewport` edge computation and scales with edge count.

## Hard limits from the code

- `rsvg-convert` subprocess timeout: 120 s (`render.py::_run`).
- Impression floor: 400 chars + 3 distinct sentences; decision rationale
  200 chars (`records.py`); advisory records share the same floor.
- Stop-hook denial budget: `max_stop_denials: 2`
  (`records-policy.json`); afterwards the session finishes with gaps
  recorded in `records-status.json`.
- MCP/CLI paths: confined to `OPENHANDS_PROJECT_DIR`
  (`workspace.py`); symlink outputs rejected; records/artifacts outside
  the workspace raise `ValueError`.
- Records-policy artifact coverage: `**/*.brief.json`,
  `**/*.intake.json`, `**/design-report.{json,md}`, `**/*.envelope.json`,
  `**/*.{step,stl,3mf,dxf}`, `**/*.ux-response.json`; `examples/`,
  `tests/`, `.devin/` ignored.
- Views sheet: fixed 2x2 layout (front/top/right/isometric), 64 max
  samples per edge, uniform scale in model units (mm).
- Parallelism: per AGENTS.md, `--jobs`-style args default
  `min(os.cpu_count() or 1, N)`; OCP compute is process-bound
  (`ProcessPoolExecutor` spawn); parallelism must not change artifacts,
  hashes, or verdicts.
- Coverage gate: pytest measures `src/mech` at ≥ 83% lines (fast stage).


## Author timing (example enclosure, this branch)

| Command | Wall time |
| --- | --- |
| `python -m mech author --brief examples/enclosure.brief.json --no-render` | ~3.1 s |
| same with renders (default) | ~4.7 s |

Renders add ~1.5 s (four DXF rasterizations + four `project_to_viewport`
sheets). Render failures never change the gate verdict — they land in
`renders: {status: "error", detail}` and must be fixed before the stage
impression.