---
name: mech-brief
description: Define and validate a provenance-bound mechanical design brief before CAD authoring.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - design brief
  - 設計ブリーフ
  - requirements intake
  - 要件整理
  - 筐体設計
---

# Mechanical design brief and intake

The brief-intake sub-agent converts conversation statements into `<name>.brief.json` and
`<name>.intake.json`. Requirements use `R*` ids, assumptions `A*`, open questions `Q*`.
Every part and mechanism feature maps to one or more source ids. The sidecar binds to
the exact brief bytes with `brief_sha256`.

## Brief schema (pydantic, extra-forbid)

```json
{
  "name": "demo",
  "design_type": "enclosure | bracket | spur_gear",
  "material": "PLA|ABS|ASA|PETG|PA|PP|PC|AL6061|SUS304",
  "process": "fdm|machining|molding|sheet_metal",
  "enclosure": { "...EnclosureSpec" },
  "bracket": { "...BracketSpec" },
  "spur_gear": { "...SpurGearSpec" },
  "mechanism_features": [],
  "fits": [],
  "stackups": []
}
```

Only the spec block matching `design_type` may be non-null. `spur_gear` does not accept
mechanism features.

## EnclosureSpec essentials

- `width_mm`/`depth_mm`/`height_mm` — outer envelope, XY-centered, floor at Z=0.
- `wall_mm`/`floor_mm`/`lid` (`screw` or `snap`) + `corner_radius_mm`/`clearance_mm`.
- `board` — keepout + `mount_holes[]` (id, x_mm, y_mm, diameter_mm).
- `standoff_height_mm`, `openings[]` (face, rect|round, width/height, center offsets),
  `vent` (face, slot_width/length/pitch, margin), `screw` (`size` M2–M12,
  `boss_diameter_mm`).
- Opening face-local coords: on front/back/left/right, `x_mm` runs tangentially along
  the wall and `y_mm` is Z centered at `height/2`. On `top`/`bottom` it maps to X/Y.

## BracketSpec essentials

- `form`: `plate` | `l` | `u`. `width_mm` is the plate Y depth, `thickness_mm` the
  stock, `base_mm` the X extent, `leg_mm` the Z leg height, `plate_length_mm` for the
  plate form. `inner_fillet_mm` and boolean `gusset`.
- `holes[]`: face `base`/`leg`/`plate`, `x_mm`/`y_mm` face-local, `diameter_mm`,
  optional `depth_mm` (null = through), `countersink_diameter_mm`.

## SpurGearSpec essentials

- `module_mm`, `teeth` (≥8), `pressure_angle_deg` (default 20), `thickness_mm`,
  `bore_mm`, optional `hub_diameter_mm`+`hub_height_mm`, `backlash_mm`.

## mechanism_features[]

`type`: `snap_fit` (modeled cantilever+hook), `rib` (modeled triangle), `boss`
(modeled cylinder+id), `living_hinge`/`detent` (parametric-only). Placement uses
`face`, `x_mm` (along wall), `y_mm` (boss: floor Y), `z_mm` (above inner floor).
Modeled features weld 0.1 mm into their host face — count that embed in stack-ups.

## fits[] and stackups[]

- `fits[]`: `{id: FT#, feature, nominal_mm, hole_class (H6–H11), shaft_class, intent}`
  — hole classes per ISO 286; `intent` is `clearance|transition|interference`.
- `stackups[]`: `{id: SC#, min_mm, max_mm, elements:[{name, nominal_mm, plus_mm, minus_mm}]}`
  — worst-case bounds and RSS.

## Intake sidecar

`part_sources`/`feature_sources` map each part/feature to `R*`/`A*`/`Q*` ids. The gate
is `ready` only when `brief_sha256` matches, every part and feature maps, all source
ids exist, and there are no open questions. Assumption-only mappings are reported but
do not block authoring.
