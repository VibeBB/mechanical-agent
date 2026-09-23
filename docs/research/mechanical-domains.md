# Mechanical design domain survey

What a conversational mechanical-design agent should cover, ordered by
implementation priority. v0.1.0 scope is marked.

## 1. Enclosure / housing design (筐体設計) — flagship, in v0.1.0

- Shell + lid (screw-fastened ridge or snap-latch skirt), floor,
  wall thickness, draft-friendly shapes.
- Board integration: PCB keepout (reference solid), standoffs (height
  above floor, boss OD/ID rules), edge clearance, connector openings.
- Openings in walls: rect/round cutouts verified by residual-material
  probe (the hole must actually pierce the wall).
- Ventilation: vent grid patterns on a face.
- Rules: DFM wall minima per process; standoff boss geometry.

## 2. Mechanism design (機構設計) — partial in v0.1.0

- **Spur gears**: involute teeth, module/teeth/pressure-angle parameters,
  undercut limit (z < 17 at α=20°), backlash bound, bore + hub. Modeled.
- **Snap-fit**: cantilever beam root strain
  ε = 1.5·t·δ/L² vs material allowable; length/thickness aspect ≥ 5.
  Modeled (beam + hook on lid or wall).
- **Ribs**: height/length, thickness vs host-wall ratio (molding ≤ 0.6·t).
  Modeled.
- **Bosses**: OD/ID ring for screws. Modeled.
- **Living hinges**: web thickness vs material capability (PP-class).
  Parametric rules only.
- **Detents**: ramp angle rules. Parametric rules only.
- Future: cam/latch linkages, gear trains (center distance, ratio),
  spring seats.

## 3. Structural parts (構造部品) — in v0.1.0

- Brackets: plate / L / U sections, inner fillet, gusset option, holes on
  declared faces.
- Future: bosses/towers, flanges, ribs-on-demand, mounting feet.

## 4. Sheet metal (板金) — rules only in v0.1.0

- Bend radius ≥ 1.0·t, hole-to-bend distance ≥ 2.5·t, wall = material
  thickness. Checked as DFM rules on declared thickness; no unfold/fold
  geometry yet.

## 5. DFM (製造性)

| Process | Checks implemented |
| --- | --- |
| FDM | min wall 0.8, min hole 1.5, min feature 0.5, overhang 45° |
| Machining | min wall 0.5, min hole 0.5, min feature 0.8, fillet 0.5 |
| Injection molding | wall 1.2–4.0, hole 1.0, feature 0.8, draft 1.0°, rib ratio 0.6, hole-to-edge 1.5·d, fillet 0.25 |
| Sheet metal | wall 0.5, hole ≥ 1.0·t, bend ≥ 1.0·t, hole-to-bend ≥ 2.5·t |

Exact values: `src/mech/standards.py` `PROCESS_LIMITS`.

## 6. Tolerancing (公差解析) — in v0.1.0

- ISO 286 hole-basis fits: H6–H11 holes × e8/f7/g6/h6/h7/h8/k6/m6/n6/p6/s6
  shafts → clearance window + class vs declared intent.
- 1-D stackups: worst-case and RSS (symmetric half-tolerance) against
  `min_mm`/`max_mm` requirement windows.

## 7. Machine elements (機械要素) — standards tables in v0.1.0

- ISO metric threads (coarse/fine pitch, tap drill).
- Bearing seats (bore/shaft seat diameters for common series).

## 8. Drawing output (図面) — DXF in v0.1.0

- Top-outline DXF per part at a chosen slice height; STEP is the
  authoritative 3D artifact.

## Future domains

Sheet-metal folding, a `fixture` design_type (jigs — softjaw patterns),
and FEA hooks (CalculiX subprocess). All future work; none is implied by
v0.1.0 APIs.

## Intake model (conversation → brief)

The agent converses to produce `intake.json`:

- `R*` requirements (speaker-tagged),
- `A*` assumptions (with rationale),
- `Q*` open questions (block the pipeline until resolved),
- `part_sources`/`feature_sources`: every generated element traces to
  requirement/assumption ids; `brief_sha256` binds intake to the brief
  (post-intake edits fail the check).

This is the L2→L1 boundary: once intake passes, the brief drives fully
deterministic generation, and nothing downstream is negotiable.
