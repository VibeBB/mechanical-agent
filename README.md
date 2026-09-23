# mechanical-agent (mech)

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/VibeBB/mechanical-agent)

Part of the [VibeBB](https://github.com/VibeBB) agent family:
[bard-agent](https://github.com/VibeBB/bard-agent) ·
[electrical-circuit-agent](https://github.com/VibeBB/electrical-circuit-agent) ·
[mechanical-agent](https://github.com/VibeBB/mechanical-agent) ·
[wire-agent](https://github.com/VibeBB/wire-agent)

[English](#english) | [日本語](#日本語)

## English

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

### What it designs (v0.1.0)

| Domain | Scope |
| --- | --- |
| Enclosures (flagship) | shell + lid (screw or snap), board keepout, standoffs, wall openings, vent patterns |
| Structures | plate / L / U brackets with holes and gussets |
| Mechanisms | spur gears (involute), snap-fit beams, ribs, bosses (modeled); living hinges and detents (parametric rules) |
| DFM | FDM, machining, injection molding, sheet-metal rule checks |
| Tolerancing | ISO 286 limits-and-fits, 1-D worst-case + RSS stackups |
| Elements | ISO metric threads, bearing seats (standards tables) |
| Drawings | DXF outlines alongside STEP/STL/3MF |

### Install

The plugin lives in `plugins/mech` and follows the OpenHands Software Agent
SDK plugin layout (skills, agents, commands, hooks, `.mcp.json`). Install it
from the OpenHands plugin UI (Agent Canvas → Customize → Plugins → Add
plugin) with:

| Field | Value |
| --- | --- |
| Source | `github:VibeBB/mechanical-agent` |
| Ref | the latest tag from [Releases](https://github.com/VibeBB/mechanical-agent/releases) |
| Path | `plugins/mech` |

Prebuilt container images are published to GHCR (`ghcr.io/vibebb/mech-tools`,
`ghcr.io/vibebb/mech-server`; digest-locked via `docker/image-digests.json`)
— see `docker/README.md` for build and run examples.

Requires Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/).

### Using the plugin

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

### Using the core directly

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
`provenance.json` (license + brief hash + tool versions), and `design-report.json` /
`design-report.md` (per-check verdicts). If any gate is `fail` or
`unknown`, the design verdict is `fail`.

### Gate coverage

kernel validity · STEP round-trip volume match · mesh validity · part
interference · board envelope & keepout · openings (residual-wall material)
· wall thickness vs process minimum · declared+measured DFM rules ·
mechanism rules (gear undercut/backlash, snap-fit strain/aspect, rib,
boss, living hinge, detent) · ISO 286 fits vs declared intent · tolerance
stackups · manifest sha256 integrity.

### Repository layout

```text
src/mech/                 # deterministic core (the only pass/fail authority)
plugins/mech/             # OpenHands plugin: skills, agents, commands, hooks, .mcp.json
tests/                    # pytest suite (includes deliberate-corruption tests)
scripts/                  # verify_all, e2e_authoring, check_plugin_load, dep checks
docs/                     # architecture, operations, ADRs, research notes
```

### Development

```bash
uv sync
uv run python scripts/verify_all.py --stage fast   # ruff + format + pyright + pytest + docs
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [docs/architecture.md](docs/architecture.md),
and the ADR index in [docs/README.md](docs/README.md).

### License

BSD-3-Clause © VibeBB — see [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## 日本語

[OpenHands](https://github.com/OpenHands) 向けの**会話型機械設計**
プラグインです。自然言語でユーザーと対話して要件を確定し、機械検査
可能な design brief に記録し、パラメトリック CAD 部品を生成して
製造成果物をエクスポートし、すべての成果物を決定論的設計ゲートで
証明します。

```text
会話 -> intake.json (R*/A*/Q*) -> design.brief.json -> 生成
  -> エクスポート (STEP/STL/3MF/DXF) -> ゲート -> design-report.json
```

合否判定は `src/mech` の決定論コアだけが行います。LLM・サブエージェント・
スキル・vision の観察は作業を導く助言に留まり、合格へ押し上げることは
できません — ツール欠落・パース失敗・不明な状態はすべて fail-closed です。

### 設計できるもの (v0.1.0)

| 領域 | スコープ |
| --- | --- |
| 筐体（主力） | シェル＋蓋（ねじ/スナップ）、基板キープアウト、スタンドオフ、壁面開口、ベントパターン |
| 構造部品 | プレート/L/U ブラケット（穴・ガセット付き） |
| 機構 | 平歯車（インボリュート）、スナップフィット梁、リブ、ボス（モデル化）、リビングヒンジとデテント（パラメトリックルール） |
| DFM | FDM、切削、射出成形、板金のルール検査 |
| 公差 | ISO 286 公差域、1次元ワーストケース＋RSS スタックアップ |
| 要素 | ISO メートルねじ、ベアリング座（標準表） |
| 図面 | STEP/STL/3MF と併せた DXF アウトライン |

### インストール

プラグインは `plugins/mech` にあり、OpenHands Software Agent SDK の
プラグイン構成（skills・agents・commands・hooks・`.mcp.json`）に従います。
OpenHands プラグイン UI（Agent Canvas → Customize → Plugins → Add plugin）
から次の値でインストールします:

| 項目 | 値 |
| --- | --- |
| Source | `github:VibeBB/mechanical-agent` |
| Ref | [Releases](https://github.com/VibeBB/mechanical-agent/releases) の最新タグ |
| Path | `plugins/mech` |

ビルド済みコンテナイメージは GHCR に公開されています
（`ghcr.io/vibebb/mech-tools`、`ghcr.io/vibebb/mech-server`。
`docker/image-digests.json` で digest 固定）。ビルド・実行例は
`docker/README.md` を参照してください。

Python ≥ 3.12 と [uv](https://docs.astral.sh/uv/) が必要です。

### プラグインの使い方

コマンド（エージェント向け）:

- `/mech:doctor` — CAD 環境の診断（カーネル・エクスポータ・依存）
- `/mech:design` — brief → 成果物 → ゲート → レポートを1設計分実行
- `/mech:gates` — 既存出力ディレクトリで全ゲートを再実行
- `/mech:export` — 成果物のみ再生成

サブエージェント（`task` ツール）: `mech-brief`（要件・intake 対話）、
`mech-design`（brief → 生成 → エクスポート）、`mech-review`（ゲート出力の
助言レビュー。投影レンダリングの vision 対応 — L2 のみ、合否権限なし）。

`mech` MCP サーバーは stdio 経由で決定論ツール（`mech_doctor`、
`mech_validate_brief`、`mech_intake`、`mech_fit_lookup`、`mech_standards`、
`mech_author`、`mech_gates`）を公開します。`.mcp.json` は
`scripts/mech_launcher.py` 経由で解決します。

### コアの直接使用

```bash
uv sync
uv run python -m mech doctor
uv run python -m mech intake --brief design.brief.json --intake intake.json
uv run python -m mech author --brief design.brief.json --out out/design
uv run python -m mech gates  --brief design.brief.json --out out/design
uv run python -m mech export --brief design.brief.json --out out/design
# ワンショットドライバ:
uv run python scripts/e2e_authoring.py --brief design.brief.json --out out/design
```

`author` は設計毎に `*.step`（アセンブリ＋各部品）、`*.stl`（各部品）、
`*.3mf`、`*.dxf` アウトライン、`manifest.json`（全ファイルの sha256）、
`provenance.json`（brief ハッシュ・ツール版・ライセンス）、
`design-report.json` / `design-report.md`（検査毎の判定）を出力します。
いずれかのゲートが `fail` または `unknown` の場合、設計判定は `fail` に
なります。

### ゲート範囲

カーネル有効性 · STEP ラウンドトリップ体積一致 · メッシュ有効性 · 部品干渉
· 基板エンベロープ＆キープアウト · 開口（残存壁材料） · プロセス最小肉厚
· 宣言＋実測の DFM ルール · 機構ルール（歯車アンダーカット/バックラッシュ、
スナップフィット歪み/アスペクト、リブ、ボス、リビングヒンジ、デテント）
· ISO 286 嵌合（宣言意図との照合） · 公差スタックアップ · マニフェスト
sha256 完全性。

### リポジトリ構成

```text
src/mech/                 # 決定論コア（唯一の合否権限）
plugins/mech/             # OpenHands プラグイン: skills, agents, commands, hooks, .mcp.json
tests/                    # pytest スイート（意図的破損テストを含む）
scripts/                  # verify_all, e2e_authoring, check_plugin_load, 依存チェック
docs/                     # アーキテクチャ、運用、ADR、調査ノート
```

### 開発

```bash
uv sync
uv run python scripts/verify_all.py --stage fast   # ruff + format + pyright + pytest + docs
```

[CONTRIBUTING.md](CONTRIBUTING.md)、[docs/architecture.md](docs/architecture.md)、
[docs/README.md](docs/README.md) の ADR 索引を参照してください。

### ライセンス

BSD-3-Clause © VibeBB — [LICENSE](LICENSE) と
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) を参照してください。
