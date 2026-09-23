---
name: mech-enclosure
description: Decide enclosure architecture — lid fastening, board mounting, openings, vents, walls.
version: 0.1.0
license: BSD-3-Clause
triggers:
  - enclosure
  - 筐体
  - housing design
  - 筐体設計
---

# Enclosure design decisions

## Lid fastening

- `lid: screw` — corner bosses in each wall corner, clearance holes in the lid. Pick
  `screw.size` M3 default (M2 for <60 mm boxes, M4 for >150 mm). Boss OD =
  `boss_diameter_mm` (default 7.0); the generator webs each boss into the adjacent
  walls (0.4 mm embed) which also strengthens the corner.
- `lid: snap` — a skirt ring hangs from the lid into the shell; a ridge on the skirt
  engages a groove in the shell wall. Engagement = min(3.0, 1.5·wall), ridge =
  min(0.6, 0.3·wall). Skirt needs flexible material — prefer ABS/PP/PA; warn on PLA.
- Assembly clearance (`clearance_mm`) is applied between lid plate and shell rim.

## Board mounting

- `board.mount_holes[]` produce standoffs on the floor: OD = hole_d + 3.0 mm,
  pilot bore = max(1.0, hole_d − 0.7) for self-tapping screws.
- `standoff_height_mm` sets component clearance under the board; the board keepout
  reference solid spans `thickness_mm + keepout_height_mm` above it — openings,
  bosses, and ribs must not intersect it (gate-checked).

## Walls and floor

- FDM: ≥ 1.2 mm wall; keep near-thinness above the process minimum after welds
  (feature weld-ins take ~0.1 mm). The gate measures the min distance between
  opposing planar faces.
- Molding: prefer uniform wall ~2 mm, draft ≥ 1° on verticals (rule-checked on
  ribs/snap beams).
- Openings must fully pierce their face — the gate verifies removed volume ≥
  50% of nominal. Round openings use `width_mm` as diameter.

## Vents

- Slots on a wall or the top: `slot_width_mm` ≥ 2 mm on FDM, pitch ≥ 2× width,
  `margin_mm` ≥ 5 mm from edges. The generator lays slots centered on the face
  within margins.

## Common gate failures

- `interference` — board keepout or boss colliding with a wall/opening/standoff.
- `openings_clear` — opening declared on a face but not piercing (blocked by a boss
  or outside the wall span).
- `wall_thickness` — min opposing-face distance; watch walls under snap grooves and
  welded features.
