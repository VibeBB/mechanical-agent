---
name: mech-dfm
description: DFM process limits, ISO 286 fits, and 1D tolerance stack-up rules.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - DFM
  - tolerance
  - fits
  - 公差
  - はめあい
---

# DFM, fits, and stack-ups

## Process limits (`mech_standards kind=processes`)

| process    | min_wall | max_wall | min_hole | min_feature | draft | extra rules |
|------------|----------|----------|----------|-------------|-------|-------------|
| fdm        | 0.8      | —        | 1.5      | 0.5         | —     | overhang ≤45° from vertical |
| machining  | 0.5      | —        | 0.5      | 0.8         | —     | internal fillet ≥0.5 mm |
| molding    | 1.2      | 4.0      | 1.0      | 0.8         | 1.0°  | rib ≤0.6×wall, hole-edge ≥1.5×d, fillet ≥0.25 |
| sheet_metal| 0.5      | —        | 1.0×t    | —           | —     | inside bend ≥1.0×t, hole-to-bend ≥2.5×t |

Rules check the declared `wall_mm`/`floor_mm`/feature dims against these plus the
*measured* minimum wall from the gate (welded features cost ~0.1 mm).

## Material quick picks

- Enclosures on FDM: ABS/ASA (tough, snap-capable), PETG (chemical-resistant), avoid
  PLA for snap fits (brittle).
- Living hinges: PP first choice, PA second.
- Structural metal parts: AL6061 machining, SUS304 for wear/corrosion.

## ISO 286 fits (`mech_fit_lookup`, `fits[]`)

Hole classes H6–H11; shaft classes e8/f7/g6/h6/js6/k6/m6/n6/p6/r6/s6 per intent:

| intent        | typical pair           |
|---------------|------------------------|
| clearance     | H7/g6, H8/e8, H11/c11  |
| transition    | H7/js6, H7/k6, H7/m6   |
| interference  | H7/p6, H7/n6, H7/s6    |

`evaluate_fit` returns the min/max clearance window and classifies the pair; a
mismatched `intent` (e.g. clearance pair declared as press) is a gate failure.
Every declared `fits[].feature` must reference a known part or mechanism feature.

## Stack-ups (`stackups[]`)

- Each element: `{name, nominal_mm, plus_mm, minus_mm}` (asymmetric allowed).
- Worst-case window = Σnominal+Σplus / Σnominal−Σminus; RSS = √(Σplus²+Σminus²).
- The gate fails when the worst-case window exceeds the declared `min_mm..max_mm`.
- Include welds (~0.1 mm per welded feature) and process tolerances as elements —
  do not shrink declared tolerances to pass.
