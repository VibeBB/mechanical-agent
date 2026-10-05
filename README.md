# mechanical-agent (mech)

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/VibeBB/mechanical-agent)

One of eleven [VibeBB](https://vibebb.org/) sister plugins:
[UX-creator](https://github.com/VibeBB/ux-creator-agent) ·
[bard](https://github.com/VibeBB/bard-agent) ·
[dashboard](https://github.com/VibeBB/dashboard-agent) ·
[document](https://github.com/VibeBB/document-agent) ·
[electrical-circuit](https://github.com/VibeBB/electrical-circuit-agent) ·
[firmware](https://github.com/VibeBB/firmware-agent) ·
[fpga](https://github.com/VibeBB/fpga-agent) ·
[mechanical](https://github.com/VibeBB/mechanical-agent) ·
[production-engineering](https://github.com/VibeBB/production-engineering-agent) ·
[simulation](https://github.com/VibeBB/simulation-agent) ·
[wire](https://github.com/VibeBB/wire-agent)

[English](#english) | [日本語](#日本語)

## English

mech lets you design mechanical parts by talking to an AI — no CAD skills
needed. Describe what you want in plain language ("an enclosure for this
board, 80×60×30, snap lid, two cable openings"), and mech turns that into
real manufacturing files it can prove correct.

### What you give / what you get

**You give:** a conversation about your requirements — dimensions,
material, how it will be made (3D print, machining, molding, sheet
metal), what it must hold or attach to. Photos or sketches help; mech can
look at them.

**You get back:** STEP/STL/3MF CAD files, dimensioned DXF drawings, and a
`design-report.json` that proves the design against deterministic gates
(wall thickness vs process minimums, openings that really pierce, fits
and tolerance stack-ups, part interference, harness anchors inside the
envelope, …). Authoring also produces advisory renders — every drawing
plus a 4-view sheet (third-angle: top/iso over front/right) of every
part and the assembly, with harness anchors marked when an envelope was
exported — so a human, or the AI's own vision, can sanity-check the
geometry.

### How it works with the sister plugins

- **UX-creator** directs the whole family: it files a request in the
  workspace `liaison/` folder and mech answers with status, gate
  verdicts, and links to its recorded design decisions.
- **wire** receives the `*.envelope.json` describing where cables clip
  or break out of the enclosure (plus a provenance sidecar).
- **simulation** and **production-engineering** consume the STEP/STL and
  the design report; **document** turns the work into documentation.
- Every sister (including mech) leaves the same reasoning records:
  design decisions from first principles, an impression at the end of
  each stage, and a vision review for every image it looked at.

### How to start

mech runs inside OpenHands / AgentCanvas. Add the plugin in the plugin UI
(Agent Canvas → Customize → Plugins → Add plugin):

| Field | Value |
| --- | --- |
| Source | `github:VibeBB/mechanical-agent` |
| Ref | the latest tag from [Releases](https://github.com/VibeBB/mechanical-agent/releases) |
| Path | `plugins/mech` |

All tools run inside the pinned `mech-tools` Docker image — nothing
extra to install. Then just ask: "design an enclosure for my board" or
use `/mech:design`.

### Limits and safety

- Pass/fail comes only from the deterministic gates — the AI can never
  "talk its way" to a pass; missing tools or unmeasurable checks fail
  the design rather than guessing.
- Generated files (STEP, DXF, reports, liaison responses) are projections
  and can't be hand-edited — everything regenerates from the brief.
- mech designs **enclosures** (shell+lid, board keepout, standoffs,
  openings, vents), **brackets**, **spur gears** and common mechanism
  features (snap-fits, ribs, bosses); living hinges and detents are
  rule-checked but not yet modeled. It does not replace a PE sign-off
  for safety-critical parts.

Technical details live in [docs/](docs/README.md) (architecture,
workflow, MCP tools, hooks, contracts, records, sister cooperation,
performance).

### License

BSD-3-Clause © VibeBB — see [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## 日本語

mech は AI と会話するだけで機械部品を設計できるプラグインです。CAD の
知識は不要です。「この基板用の 80×60×30 の筐体、スナップ蓋、ケーブル
開口2つ」のように自然言語で伝えると、それを実際の製造ファイルに
変換し、正しさを証明します。

### 入力と出力

**入力:** 要件の会話 — 寸法、材質、製造方法（3Dプリント・切削・射出
成形・板金）、何を収めて何に固定するか。写真やスケッチがあれば
mech が見て取り入れます。

**出力:** STEP/STL/3MF の CAD ファイル、寸法入り DXF 図面、そして
決定論的ゲートで証明した `design-report.json`（工程最小肉厚、実際に
貫通する開口、嵌合・公差積み上げ、部品干渉、筐体内のハーネスアンカー
など）。作図時にアドバイザリのレンダリングも生成します — 全図面と各部品・
アセンブリの4面図シート（第三角法：上段が上面/アイソメ、下段が正面/右側面、
エンベロープ出力済みならアンカー表示付き）— で、人や AI の vision が
幾何を確認できます。

### 姉妹プラグインとの連携

- **UX-creator** がファミリー全体を指揮します：ワークスペースの
  `liaison/` に依頼を出し、mech はステータス・ゲート判定・記録済み
  設計判断への参照で応答します。
- **wire** へはケーブルのクリップ位置や引き出し口を表す
  `*.envelope.json`（＋来歴サイドカー）を渡します。
- **simulation** と **production-engineering** は STEP/STL と
  設計レポートを、**document** は作業内容をドキュメント化に使います。
- すべての姉妹（mech も）は同じ推論レコードを残します：第一原理からの
  設計決定、各ステージ終了時の印象、見た画像すべての vision レビュー。

### 始め方

mech は OpenHands / AgentCanvas 内で動きます。プラグイン UI（Agent
Canvas → Customize → Plugins → Add plugin）で次を指定します：

| 項目 | 値 |
| --- | --- |
| Source | `github:VibeBB/mechanical-agent` |
| Ref | [Releases](https://github.com/VibeBB/mechanical-agent/releases) の最新タグ |
| Path | `plugins/mech` |

ツールはすべて固定された `mech-tools` Docker イメージ内で動くため、
追加インストールは不要です。「基板の筐体を設計して」と頼むか
`/mech:design` を使うだけです。

### 制限と安全性

- 合否は決定論的ゲートだけが出します — AI が「口で」合格にすることは
  できず、ツール欠落や測定不能は設計を失敗にします。
- 生成ファイル（STEP・DXF・レポート・liaison 応答）は射影であり手編集
  できません — すべて brief から再生成します。
- 設計できるのは**筐体**（シェル＋蓋・基板キープアウト・スタンドオフ・
  開口・ベント）、**ブラケット**、**平歯車**、一般的な機構フィーチャ
  （スナップ・リブ・ボス）です。リビングヒンジとデテントはルール検査
  のみで未モデル化です。安全上重要な部品の設計者サインオフを代替する
  ものではありません。

技術詳細は [docs/](docs/README.md)（アーキテクチャ・ワークフロー・
MCP ツール・フック・契約・レコード・姉妹連携・性能）を参照してください。

### ライセンス

BSD-3-Clause © VibeBB — [LICENSE](LICENSE) と
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) を参照。
