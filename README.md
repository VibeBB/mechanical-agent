# mechanical-agent (mech)

An [OpenHands](https://github.com/OpenHands) plugin for **conversational
mechanical design**: it talks with the user in natural language to pin down
requirements, records them in a machine-checked design brief, generates
parametric CAD parts, exports manufacturing artifacts, and proves every
artifact against deterministic design gates.

```text
conversation -> intake.json (R*/A*/Q*) -> design.brief.json -> generate
  -> export (STEP/STL/3MF/DXF) -> gates -> design-report.json
```

All pass/fail verdicts come only from the deterministic core in `src/mech`.
LLMs, sub-agents, skills, and vision observations steer the work but can
never promote anything to a pass — missing tools, parse failures, and
unknowns are fail-closed.

## What it designs (v0.1.0)

| Domain | Scope |
| --- | --- |
| Enclosures (flagship) | shell + lid (screw or snap), board keepout, standoffs, wall openings, vent patterns |
| Structures | plate / L / U brackets with holes and gussets |
| Mechanisms | spur gears (involute), snap-fit beams, ribs, bosses (modeled); living hinges and detents (parametric rules) |
| DFM | FDM, machining, injection molding, sheet-metal rule checks |
| Tolerancing | ISO 286 limits-and-fits, 1-D worst-case + RSS stackups |
| Elements | ISO metric threads, bearing seats (standards tables) |
| Drawings | DXF outlines alongside STEP/STL/3MF |

Copyleft kernels (FreeCAD, OpenSCAD, CalculiX, gmsh) are deliberately not
import-linked; see [docs/adr/ADR-0001](docs/adr/ADR-0001-cad-kernel.md).

## Install

The plugin lives in `plugins/mech` and follows the OpenHands Software Agent
SDK plugin layout (skills, agents, commands, hooks, `.mcp.json`). Point the
agent at this repository or install `plugins/mech` into your OpenHands
plugin store.

Requires Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/).

## Using the plugin

Commands (agent-facing):

- `/mech:doctor` — probe the CAD environment (kernel, exporters, deps)
- `/mech:design` — drive brief → artifacts → gates → report for one design
- `/mech:gates` — re-run all gates on an existing output directory
- `/mech:export` — regenerate artifacts only

Sub-agents (`task` tool): `mech-brief` (requirement/intake conversation),
`mech-design` (brief → generation → export), `mech-review` (advisory review
of gate output; vision-capable for rendered projections — L2 only, no
pass/fail authority).

The `mech` MCP server exposes deterministic tools (`mech_doctor`,
`mech_validate_brief`, `mech_intake`, `mech_fit_lookup`, `mech_standards`,
`mech_author`, `mech_gates`) over stdio; `.mcp.json` resolves it through
`scripts/mech_launcher.py`.

## Using the core directly

```bash
uv sync
uv run python -m mech doctor
uv run python -m mech intake --brief design.brief.json --intake intake.json
uv run python -m mech author --brief design.brief.json --out out/design
uv run python -m mech gates  --brief design.brief.json --out out/design
uv run python -m mech export --brief design.brief.json --out out/design
# or the one-shot driver:
uv run python scripts/e2e_authoring.py --brief design.brief.json --out out/design
```

`author` emits, per design: `*.step` (assembly + per part), `*.stl` (per
part), `*.3mf`, `*.dxf` outlines, `manifest.json` (sha256 of every file),
`provenance.json` (brief hash + tool versions), and `design-report.json` /
`design-report.md` (per-check verdicts). If any gate is `fail` or
`unknown`, the design verdict is `fail`.

## Gate coverage

kernel validity · STEP round-trip volume match · mesh validity · part
interference · board envelope & keepout · openings (residual-wall material)
· wall thickness vs process minimum · declared+measured DFM rules ·
mechanism rules (gear undercut/backlash, snap-fit strain/aspect, rib,
boss, living hinge, detent) · ISO 286 fits vs declared intent · tolerance
stackups · manifest sha256 integrity.

## Repository layout

```text
src/mech/                 # deterministic core (the only pass/fail authority)
plugins/mech/             # OpenHands plugin: skills, agents, commands, hooks, .mcp.json
tests/                    # pytest suite (includes deliberate-corruption tests)
scripts/                  # verify_all, e2e_authoring, check_plugin_load, dep checks
docs/                     # architecture, operations, ADRs, research notes
```

## Development

```bash
uv sync
uv run python scripts/verify_all.py --stage fast   # ruff + format + pyright + pytest + docs
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [docs/architecture.md](docs/architecture.md),
and the ADR index in [docs/README.md](docs/README.md).

## License

BSD-3-Clause © Y.Yamashiro — see [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

## 日本語

mechanical-agent (mech) は、自然言語でユーザーと対話しながら設計要件を
定め、機械設計（筐体設計・機構設計・構造部品・DFM・公差解析）を実施する
OpenHands プラグインです。`src/mech` の決定論コアだけが合否を判定し、
LLM・サブエージェント・vision の観察は助言に留まり、未実行・不明は
fail-closed として不合格扱いになります。

- 会話 → `intake.json`（要求 R/仮定 A/質問 Q と部品・フィーチャの対応付け）
- `design.brief.json` → パラメトリック生成 → STEP/STL/3MF/DXF 出力
- 全ゲートを実行し `design-report.json` に判定を記録
- 主要コマンド: `/mech:design` `/mech:doctor` `/mech:gates` `/mech:export`

詳細は上記の英語本文と [docs/](docs/README.md) を参照してください。
