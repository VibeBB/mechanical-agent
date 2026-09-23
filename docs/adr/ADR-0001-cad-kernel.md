# ADR-0001: CAD kernel selection — build123d; copyleft tools stay subprocess-only

- Status: Accepted
- Date: 2026-09-23

## Context

mech needs a BRep CAD kernel for parametric generation (enclosures,
brackets, gears), boolean work, measurement (volume, distance,
bounding boxes, wall thickness via section bands), and manufacturing
export (STEP, STL, 3MF, DXF). The project is BSD-3-Clause OSS and must
not import-bind copyleft code (AGENTS invariants).

## Survey summary

| Candidate | License | Distribution | Verdict |
| --- | --- | --- | --- |
| build123d 0.11.1 | Apache-2.0 | PyPI wheel, bundles OCP (OCCT 7.9) + ezdxf | Adopt |
| CadQuery | Apache-2.0 | PyPI wheel, same OCP kernel | Rejected — family standard is build123d; no extra capability needed |
| FreeCAD | LGPL-2.0+ | No PyPI wheel; own interpreter | subprocess adapter only |
| OpenSCAD | GPL-2.0+ | external binary | subprocess adapter only |
| CalculiX | GPL | external binary | subprocess adapter only (future FEA) |
| gmsh | GPL (+ limited exception) | external binary | subprocess adapter only |

## Decision

`build123d==0.11.1` is the sole import-linked CAD kernel
(`src/mech/generators/common.py` lazy-imports it so schema modules stay
importable without OCP). Exports: STEP/STL via OCCT, 3MF via `Mesher`
(lib3mf), DXF via `ExportDXF` (ezdxf, MIT).

FreeCAD, OpenSCAD, CalculiX, and gmsh may only ever run as **unmodified
subprocesses behind an adapter** — never import-linked, never re-linked
through FFI. That is an invariant, not a preference.

## Kernel quirks encoded in the generators

Verified empirically against 0.11.1 (see
[../research/cad-kernels.md](../research/cad-kernels.md)):

- `export_step`/`export_stl`/`Mesher.add_shape` reject `Part` wrapper
  objects; all exports wrap `b.Compound(children=[part.shape])`.
- Tangent/coplanar unions (a feature face lying exactly on the host face)
  produce non-manifold triangulations → `RuntimeError("3mf mesh is
  invalid")` at `mesher.write`. All mount sites embed a small "weld"
  (0.1–0.4 mm) into the host instead.
- OCCT `is_valid` stays `True` for tangent unions, so the 3mf/mesh gate
  checks are stricter than the kernel check — both are kept.

## Consequences

- Permissive stack: everything import-linked is MIT/Apache/BSD-compatible
  with BSD-3 (THIRD_PARTY_NOTICES.md).
- No FEA in v0.1.0; when added it will be a CalculiX subprocess adapter.
- OCCT rides with the build123d pin; OCP version is recorded per design in
  `provenance.json`.
