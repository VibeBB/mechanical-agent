# CAD kernel research notes

Basis for ADR-0001. Verified against build123d 0.11.1 during implementation
(2026-09).

## Candidates

### build123d 0.11.1 — adopted

- Apache-2.0, PyPI wheel, bundles OCP (OCCT 7.9.x) + ezdxf.
- Full BRep: `Box`, `Cylinder`, `extrude`, `sweep`, `loft`, booleans,
  `fillet`, `chamfer`, `Pos`/`Locations`, `Compound`.
- Exports: `export_step`, `export_stl`, `Mesher` (3mf via lib3mf),
  `ExportDXF`.
- Measurements: `shape.volume`, `shape.is_valid` (property), bounding
  boxes, `faces()` filters (`filter_by(b.Plane.XY)` works on faces),
  boolean-`&` residuals for wall/opening probes.

### CadQuery

Same OCP kernel, Apache-2.0, fluent API. Rejected: the family standard is
build123d (same kernel, consistent idioms); nothing CadQuery offers is
needed here.

### FreeCAD

LGPL-2.0-or-later. No PyPI wheel; its Python API (`import FreeCAD`)
requires the bundled interpreter. Would give parametric sketches, FEM,
TechDraw — but copyleft + packaging burden. Decision: never import; a
future adapter would run the FreeCAD binary as an unmodified subprocess.

### OpenSCAD

GPL-2.0-or-later, CGAL-based CSG, STL/OFF/3MF out, weak STEP story.
Decision: never import; subprocess only if ever needed.

### CalculiX

GPL. FEA solver (`ccx` binary) for a future structural-analysis adapter.
Decision: subprocess only.

### gmsh

GPL-2.0-or-later (plus a limited exception for generated meshes). Would
mesh STEP→FEA grids. Decision: subprocess only.

### Others evaluated

- trimesh (MIT): triangle-mesh lib, not a BRep kernel — insufficient
  (no true boolean/STEP); could later serve as an optional mesh probe.
- ezdxf (MIT): DXF writer bundled inside build123d — used.
- CadQuery/skdl/solidpython2/Blender API: GPL or non-kernel — rejected.

## build123d 0.11.1 quirks (empirically verified)

1. **`Part` wrapper objects are rejected by exporters.** `export_step`,
   `export_stl`, and `Mesher.add_shape` all fail on `Part` (an
   Algebra-mode `Compound` subclass carrying builder context). Fix:
   always export `b.Compound(children=[part.shape])`.
2. **Tangent/coplanar unions → non-manifold 3mf.** When a feature's base
   face lies exactly on the host face (standoff floor, boss on inner
   wall, rib on plate), the triangulation fails lib3mf `IsValid()` and
   `mesher.write` raises `RuntimeError("3mf mesh is invalid")`. Fix:
   embed the feature 0.1–0.4 mm into the host ("weld"): standoffs start
   `WELD_MM` below the floor; webbed bosses embed `min(0.4, radius/4)`;
   ribs/beams embed 0.1 mm.
3. **OCCT `is_valid` stays `True` for tangent unions.** The BRep itself
   is legal; only the mesh degenerates. The mesh gate therefore checks
   stricter properties than the kernel gate — both are retained.
4. **`Mesher.add_shape(shape, linear_deflection=...)`** controls 3mf
   density; the same deflection constant is used by `export_stl` for
   parity between the artifacts.
5. **`_top_outline` slicing**: slicing a part at a chosen Z with a planar
   section and exporting the outline via `ExportDXF` produces usable 2D
   drawing geometry without a full drawing package.
6. **`filter_by(b.Plane.XY)`** works on faces for the wall-thickness and
   opening residual probes (dominant-face selection by area ≥5% of group
   max, then per-face wall-band residual check).

## License compatibility

| Component | License | Link type | OK? |
| --- | --- | --- | --- |
| build123d | Apache-2.0 | import | yes |
| OCP/OCCT | LGPL-2.1 + exception | dynamic lib via build123d wheel | yes (exception clause covers library use) |
| ezdxf | MIT | import via build123d | yes |
| lib3mf | BSD | inside the wheel | yes |
| FreeCAD | LGPL | never import | subprocess only |
| OpenSCAD | GPL-2.0+ | never import | subprocess only |
| CalculiX | GPL | never import | subprocess only |
| gmsh | GPL | never import | subprocess only |
