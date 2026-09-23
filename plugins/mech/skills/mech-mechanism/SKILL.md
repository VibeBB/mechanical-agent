---
name: mech-mechanism
description: Rules for gears, snap fits, ribs, bosses, living hinges, and detents.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - mechanism
  - gear
  - snap fit
  - 機構設計
  - スナップフィット
  - リブ
---

# Mechanism rules

## Spur gears (involute, `design_type: spur_gear`)

- `module_mm` × `teeth` sets the pitch diameter. Standard pressure angle 20°.
- Dedendum = 1.25·m; tooth profile is a true involute with a rigid rotation for
  backlash. `backlash_mm` ≤ 0.2·m is enforced by the gear rules check.
- Undercut: standard 20° teeth undercut below ~17 teeth; the rule check fails
  `teeth < 17` for 20° and `teeth < 14` for 25° unless corrected (not supported —
  choose more teeth or a smaller module).
- `hub_diameter_mm` > `bore_mm` and < root diameter; hub extends +Z by
  `hub_height_mm`.
- Bore/shaft interface belongs in `fits[]` (e.g. H7/g6 sliding, H7/k6 location,
  H7/n6 light press, H7/s6 press).

## Snap fits (modeled `snap_fit`)

- Cantilever on an inner wall: `length_mm`, `width_mm`, `hook_thickness_mm`,
  `deflection_mm`. Rule check: beam strain ≈ 1.09·t·y/L² must stay under the
  material `snap_strain_limit` (PLA 1.2%, ABS/ASA 3%, PETG 2%, PA/PP 5–6%, PC 1.5%).
- Keep length ≥ 5× thickness and thickness ≥ process min feature.
- The hook protrudes `deflection_mm` toward the wall — that interference is what the
  mating catch must clear on assembly.

## Ribs (modeled `rib`)

- Triangle on a wall: `length_mm` into the cavity × `height_mm` up the wall,
  `thickness_mm` centered. Molding rule: thickness ≤ 60% of the wall it attaches to;
  otherwise sink marks.
- FDM rib thickness ≥ 1.0 mm.

## Bosses (modeled `boss`)

- Cylinder on the floor at (`x_mm`,`y_mm`): `od_mm`/`id_mm`/`height_mm`.
- Rule check: `od ≥ id + 3 mm` (enough wall for self-tapping), `height ≤ 5×od`,
  `id ≥ process min hole diameter`.
- Standoff geometry rule (`check_standoff_bosses`): `od = hole_d + 3.0`,
  `pilot = max(1.0, hole_d − 0.7)` — the generated standoffs follow it.

## Living hinges (parametric-only `living_hinge`)

- Web thickness rules: 0.2–0.5 mm target; PP preferred, PA acceptable; warn on
  other resins. Modeled geometry is out of scope — the declaration drives rules
  and documentation.

## Detents (parametric-only `detent`)

- `ramp_angle_deg` 20–45° for ball/spring detents; check `depth_mm` ≤ half the
  mating travel. Parametric validation only.
