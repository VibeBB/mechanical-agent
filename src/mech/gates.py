"""Deterministic design gates.

Every check emits a structured result: status is "pass", "fail", or
"unknown"; "unknown" and "fail" both make the design verdict fail
(fail-closed). Parametric checks (DFM, mechanism rules, fits, stack-ups)
operate on the brief; geometric checks measure the generated solids and the
exported artifacts (STEP reload, STL facet analysis, manifest hashes).
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from . import dfm as dfm_rules
from . import fits as fits_rules
from . import mechanism as mech_rules
from . import stackup as stackup_rules
from .brief import DesignBrief, EnclosureSpec, brief_sha256
from .generators.common import GeneratedDesign, build123d

CheckStatus = Literal["pass", "fail", "unknown"]

_INTERFERENCE_TOL_MM3 = 0.01
_MESH_VOLUME_TOL = 0.05  # relative
_MESH_BBOX_TOL_MM = 0.6
_AXIS_DOT_TOL = 0.99


@dataclass(frozen=True)
class GateCheck:
    id: str
    subject: str
    status: CheckStatus
    measured: float | None = None
    limit: float | None = None
    detail: str = ""


@dataclass(frozen=True)
class GateReport:
    checks: list[GateCheck]
    verdict: Literal["pass", "fail"]

    def to_dict(self, brief: DesignBrief) -> dict[str, Any]:
        summary = {
            "pass": sum(1 for c in self.checks if c.status == "pass"),
            "fail": sum(1 for c in self.checks if c.status == "fail"),
            "unknown": sum(1 for c in self.checks if c.status == "unknown"),
        }
        return {
            "schema_version": 1,
            "gate": "mech-design",
            "design": {
                "name": brief.name,
                "design_type": brief.design_type,
                "material": brief.material,
                "process": brief.process,
                "brief_sha256": brief_sha256(brief),
            },
            "checks": [
                {
                    "id": c.id,
                    "subject": c.subject,
                    "status": c.status,
                    "measured": c.measured,
                    "limit": c.limit,
                    "detail": c.detail,
                }
                for c in self.checks
            ],
            "summary": summary,
            "verdict": self.verdict,
        }


def _aggregate(checks: list[GateCheck]) -> GateReport:
    verdict: Literal["pass", "fail"] = (
        "pass" if checks and all(c.status == "pass" for c in checks) else "fail"
    )
    return GateReport(checks=checks, verdict=verdict)


# --- kernel validity -------------------------------------------------------


def _kernel_checks(design: GeneratedDesign) -> list[GateCheck]:
    checks: list[GateCheck] = []
    for part in design.parts:
        shape = part.shape
        try:
            valid = bool(shape.is_valid) and float(shape.volume) > 0.0
            checks.append(
                GateCheck(
                    "kernel_valid",
                    part.part_id,
                    "pass" if valid else "fail",
                    measured=round(float(shape.volume), 4),
                    detail="is_valid and positive volume",
                )
            )
        except Exception as exc:  # fail-closed on kernel errors
            checks.append(GateCheck("kernel_valid", part.part_id, "unknown", detail=str(exc)))
    return checks


def _reload_checks(design: GeneratedDesign, out_dir: Path, name: str) -> list[GateCheck]:
    """Reload each exported per-part STEP and compare volume to the solid."""
    b = build123d()
    checks: list[GateCheck] = []
    for part in design.parts:
        path = out_dir / f"{name}-{part.part_id}.step"
        if not path.exists():
            checks.append(
                GateCheck(
                    "reload_valid",
                    part.part_id,
                    "unknown",
                    detail=f"missing artifact {path.name}",
                )
            )
            continue
        try:
            reloaded = b.import_step(str(path))
            ok = bool(reloaded.is_valid) and abs(reloaded.volume - part.shape.volume) < max(
                1e-4 * abs(part.shape.volume), 1e-3
            )
            checks.append(
                GateCheck(
                    "reload_valid",
                    part.part_id,
                    "pass" if ok else "fail",
                    measured=round(float(reloaded.volume), 4),
                    detail="STEP round-trip validity and volume match",
                )
            )
        except Exception as exc:
            checks.append(GateCheck("reload_valid", part.part_id, "unknown", detail=str(exc)))
    return checks


# --- STL mesh --------------------------------------------------------------


@dataclass(frozen=True)
class _StlStats:
    facets: int
    volume_mm3: float
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]


def _stl_stats(path: Path) -> _StlStats:
    """Parse a binary STL: facet count, signed volume (divergence), bbox."""
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError("STL shorter than the binary header")
    facets = struct.unpack_from("<I", data, 80)[0]
    if len(data) < 84 + facets * 50:
        raise ValueError("STL truncated facet data")
    mins = [float("inf")] * 3
    maxs = [float("-inf")] * 3
    volume = 0.0
    offset = 84
    for _ in range(facets):
        v1 = struct.unpack_from("<3f", data, offset + 12)
        v2 = struct.unpack_from("<3f", data, offset + 24)
        v3 = struct.unpack_from("<3f", data, offset + 36)
        volume += (
            v1[0] * (v2[1] * v3[2] - v2[2] * v3[1])
            - v1[1] * (v2[0] * v3[2] - v2[2] * v3[0])
            + v1[2] * (v2[0] * v3[1] - v2[1] * v3[0])
        ) / 6.0
        for v in (v1, v2, v3):
            for i in range(3):
                mins[i] = min(mins[i], v[i])
                maxs[i] = max(maxs[i], v[i])
        offset += 50
    return _StlStats(
        facets=facets,
        volume_mm3=volume,
        bbox_min=(mins[0], mins[1], mins[2]),
        bbox_max=(maxs[0], maxs[1], maxs[2]),
    )


def _mesh_checks(design: GeneratedDesign, out_dir: Path, name: str) -> list[GateCheck]:
    checks: list[GateCheck] = []
    for part in design.parts:
        path = out_dir / f"{name}-{part.part_id}.stl"
        if not path.exists():
            checks.append(
                GateCheck("mesh_consistency", part.part_id, "unknown", detail="missing STL")
            )
            continue
        try:
            stats = _stl_stats(path)
            step_vol = float(part.shape.volume)
            vol_ok = abs(stats.volume_mm3 - step_vol) <= _MESH_VOLUME_TOL * step_vol
            box = part.shape.bounding_box()
            bbox_ok = (
                abs(stats.bbox_min[0] - box.min.X) < _MESH_BBOX_TOL_MM
                and abs(stats.bbox_min[1] - box.min.Y) < _MESH_BBOX_TOL_MM
                and abs(stats.bbox_min[2] - box.min.Z) < _MESH_BBOX_TOL_MM
                and abs(stats.bbox_max[0] - box.max.X) < _MESH_BBOX_TOL_MM
                and abs(stats.bbox_max[1] - box.max.Y) < _MESH_BBOX_TOL_MM
                and abs(stats.bbox_max[2] - box.max.Z) < _MESH_BBOX_TOL_MM
            )
            ok = stats.facets > 0 and vol_ok and bbox_ok
            checks.append(
                GateCheck(
                    "mesh_consistency",
                    part.part_id,
                    "pass" if ok else "fail",
                    measured=round(stats.volume_mm3, 4),
                    limit=round(step_vol, 4),
                    detail=(
                        f"{stats.facets} facets; STL volume and bbox match STEP within tolerances"
                    ),
                )
            )
        except Exception as exc:
            checks.append(GateCheck("mesh_consistency", part.part_id, "unknown", detail=str(exc)))
    return checks


# --- interference and envelope --------------------------------------------


def _interference_checks(design: GeneratedDesign) -> list[GateCheck]:
    checks: list[GateCheck] = []
    solids = [(p.part_id, p.shape) for p in design.parts] + [
        (r.reference_id, r.shape) for r in design.references
    ]
    for i in range(len(solids)):
        for j in range(i + 1, len(solids)):
            id_a, shape_a = solids[i]
            id_b, shape_b = solids[j]
            try:
                volume = float((shape_a & shape_b).volume)
            except Exception as exc:
                checks.append(
                    GateCheck(
                        "interference",
                        f"{id_a}~{id_b}",
                        "unknown",
                        detail=str(exc),
                    )
                )
                continue
            checks.append(
                GateCheck(
                    "interference",
                    f"{id_a}~{id_b}",
                    "pass" if volume < _INTERFERENCE_TOL_MM3 else "fail",
                    measured=round(volume, 4),
                    limit=_INTERFERENCE_TOL_MM3,
                )
            )
    return checks


def _board_envelope_checks(brief: DesignBrief) -> list[GateCheck]:
    spec = brief.enclosure
    if spec is None or spec.board is None:
        return []
    board = spec.board
    inner_w = spec.width_mm - 2 * spec.wall_mm
    inner_d = spec.depth_mm - 2 * spec.wall_mm
    checks = [
        GateCheck(
            "board_envelope",
            "width",
            "pass" if board.width_mm + 2 * spec.clearance_mm <= inner_w + 1e-9 else "fail",
            measured=board.width_mm,
            limit=round(inner_w - 2 * spec.clearance_mm, 4),
            detail="board width plus clearance vs cavity width",
        ),
        GateCheck(
            "board_envelope",
            "depth",
            "pass" if board.depth_mm + 2 * spec.clearance_mm <= inner_d + 1e-9 else "fail",
            measured=board.depth_mm,
            limit=round(inner_d - 2 * spec.clearance_mm, 4),
            detail="board depth plus clearance vs cavity depth",
        ),
    ]
    board_top = (
        spec.floor_mm + spec.standoff_height_mm + board.thickness_mm + board.keepout_height_mm
    )
    checks.append(
        GateCheck(
            "board_envelope",
            "height",
            "pass" if board_top <= spec.height_mm - spec.wall_mm + 1e-9 else "fail",
            measured=board_top,
            limit=round(spec.height_mm - spec.wall_mm, 4),
            detail="board keepout top below the lid underside",
        )
    )
    return checks


# --- circuit board geometry ------------------------------------------------


def _board_geometry_checks(brief: DesignBrief, geometry_path: Path | None) -> list[GateCheck]:
    from .board_geometry import (
        DIMENSION_TOL_MM,
        HOLE_TOL_MM,
        along_span,
        load_geometry,
        sha256_file,
    )

    spec = brief.enclosure
    if spec is None or spec.board is None or spec.board.source is None:
        return []
    board, source = spec.board, spec.board.source
    if geometry_path is None or not geometry_path.is_file():
        return [GateCheck("board_geometry", "source", "unknown", detail="pinned geometry missing")]
    actual = sha256_file(geometry_path)
    if actual != source.sha256:
        return [
            GateCheck(
                "board_geometry",
                "source",
                "fail",
                detail=f"stale pin: file sha256 {actual} != brief {source.sha256}",
            )
        ]
    try:
        geometry = load_geometry(geometry_path)
    except ValueError as exc:
        return [GateCheck("board_geometry", "source", "unknown", detail=str(exc))]
    if geometry.verdict != "pass":
        return [
            GateCheck(
                "board_geometry",
                "source",
                "unknown",
                detail=f"circuit geometry incomplete: {geometry.unknown}",
            )
        ]
    checks = [GateCheck("board_geometry", "source", "pass", detail=geometry.pcb.sha256)]
    for subject, declared, measured in (
        ("width", board.width_mm, geometry.width_mm),
        ("depth", board.depth_mm, geometry.depth_mm),
        ("thickness", board.thickness_mm, geometry.thickness_mm),
    ):
        assert measured is not None
        checks.append(
            GateCheck(
                "board_geometry",
                subject,
                "pass" if abs(declared - measured) <= DIMENSION_TOL_MM + 1e-9 else "fail",
                measured=measured,
                limit=declared,
                detail="brief board vs circuit Edge.Cuts/stackup",
            )
        )
    top = geometry.max_height_top_mm or 0.0
    checks.append(
        GateCheck(
            "board_geometry",
            "keepout_height",
            "pass" if board.keepout_height_mm + 1e-9 >= top else "fail",
            measured=top,
            limit=board.keepout_height_mm,
            detail="tallest top-side part vs brief keepout",
        )
    )
    unmatched = [
        hole.ref
        for hole in geometry.mount_holes
        if not any(
            abs(hole.x_mm - mh.x_mm) <= HOLE_TOL_MM + 1e-9
            and abs(hole.y_mm - mh.y_mm) <= HOLE_TOL_MM + 1e-9
            and abs(hole.diameter_mm - mh.diameter_mm) <= HOLE_TOL_MM + 1e-9
            for mh in board.mount_holes
        )
    ]
    holes_ok = not unmatched and len(board.mount_holes) == len(geometry.mount_holes)
    checks.append(
        GateCheck(
            "board_geometry",
            "mount_holes",
            "pass" if holes_ok else "fail",
            measured=len(geometry.mount_holes),
            limit=len(board.mount_holes),
            detail=f"unmatched circuit holes: {unmatched}" if unmatched else "hole sets match",
        )
    )
    board_bottom = spec.floor_mm + spec.standoff_height_mm
    board_top = board_bottom + board.thickness_mm
    for part in geometry.components:
        if not part.connector or part.edge is None or part.bbox_mm is None:
            continue
        assert part.height_mm is not None
        low, high = along_span(part)
        z0, z1 = (
            (board_top, board_top + part.height_mm)
            if part.side == "top"
            else (board_bottom - part.height_mm, board_bottom)
        )
        served = False
        for opening in spec.openings:
            if opening.face != part.edge:
                continue
            span_z = opening.height_mm if opening.kind == "rect" else opening.width_mm
            oz = spec.height_mm / 2 + opening.center_y_mm
            covers = (
                opening.center_x_mm - opening.width_mm / 2 <= low + 1e-9
                and opening.center_x_mm + opening.width_mm / 2 >= high - 1e-9
            )
            if covers and min(oz + span_z / 2, z1) - max(oz - span_z / 2, z0) > 0:
                served = True
        checks.append(
            GateCheck(
                "board_geometry",
                f"connector:{part.ref}",
                "pass" if served else "fail",
                detail=(
                    f"{part.edge} face opening must span {low:g}..{high:g} mm and "
                    f"z {z0:g}..{z1:g} mm"
                ),
            )
        )
    return checks


# --- harness anchors --------------------------------------------------------


_ANCHOR_TOL_MM = 1.0


def _harness_anchor_checks(brief: DesignBrief, design: GeneratedDesign) -> list[GateCheck]:
    """Declared anchors sit inside the assembly bbox (anchor frame = bbox min corner)."""
    anchors = [a for a in brief.harness_anchors if a.position_mm is not None]
    if not anchors:
        return []
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    try:
        for part in design.parts:
            box = part.shape.bounding_box()
            for i, (mn, mx) in enumerate(
                ((box.min.X, box.max.X), (box.min.Y, box.max.Y), (box.min.Z, box.max.Z))
            ):
                lo[i] = min(lo[i], float(mn))
                hi[i] = max(hi[i], float(mx))
    except Exception as exc:
        return [
            GateCheck(
                "harness_anchor.within_envelope",
                brief.name,
                "unknown",
                detail=f"assembly bbox failed: {exc}",
            )
        ]
    size = [hi[i] - lo[i] for i in range(3)]
    checks: list[GateCheck] = []
    for anchor in anchors:
        pos = anchor.position_mm
        assert pos is not None
        inside = all(-_ANCHOR_TOL_MM <= pos[i] <= size[i] + _ANCHOR_TOL_MM for i in range(3))
        checks.append(
            GateCheck(
                "harness_anchor.within_envelope",
                anchor.name,
                "pass" if inside else "fail",
                measured=round(max(pos), 4),
                limit=round(max(size) + _ANCHOR_TOL_MM, 4),
                detail=(
                    f"position_mm {tuple(round(v, 3) for v in pos)} vs assembly "
                    f"size {tuple(round(v, 3) for v in size)} mm (anchor frame = "
                    "assembly bbox min corner)"
                ),
            )
        )
    return checks


# --- openings and wall thickness ------------------------------------------


def _opening_checks(brief: DesignBrief, design: GeneratedDesign) -> list[GateCheck]:
    """Each declared opening must actually pierce its host part."""
    spec = brief.enclosure
    if spec is None or not spec.openings:
        return []
    from .generators.enclosure import opening_prism

    parts = {part.part_id: part.shape for part in design.parts}
    checks: list[GateCheck] = []
    for opening in spec.openings:
        host_id = "lid" if opening.face == "top" else "shell"
        host = parts.get(host_id)
        if host is None:
            checks.append(GateCheck("openings_clear", opening.id, "unknown", detail="host missing"))
            continue
        prism = opening_prism(spec, opening, spec.height_mm - spec.wall_mm)
        # The prism intersecting the finished host is ~0 by definition — the
        # hole is already cut. Measure instead the residual material: what is
        # left of the prism inside the wall band. removed = nominal - residual.
        band = _wall_band(spec, opening.face)
        try:
            passage = prism & band
            residual = float((passage & host).volume)
            banded = float(passage.volume)
        except Exception as exc:
            checks.append(GateCheck("openings_clear", opening.id, "unknown", detail=str(exc)))
            continue
        nominal = (
            3.1416 * (opening.width_mm / 2) ** 2
            if opening.kind == "round"
            else opening.width_mm * opening.height_mm
        ) * spec.wall_mm
        removed = banded - residual
        checks.append(
            GateCheck(
                "openings_clear",
                opening.id,
                "pass" if removed > 0.5 * nominal else "fail",
                measured=round(removed, 4),
                limit=round(0.5 * nominal, 4),
                detail=f"material removed through {opening.face} wall",
            )
        )
    return checks


def _wall_band(spec: EnclosureSpec, face: str) -> Any:
    """Box spanning exactly the wall/floor/lid band of the named face."""
    b = build123d()
    w, d, h = spec.width_mm, spec.depth_mm, spec.height_mm
    t, f = spec.wall_mm, spec.floor_mm
    if face == "front":
        return b.Pos(0, -d / 2 + t / 2, h / 2) * b.Box(w, t, h)
    if face == "back":
        return b.Pos(0, d / 2 - t / 2, h / 2) * b.Box(w, t, h)
    if face == "left":
        return b.Pos(-w / 2 + t / 2, 0, h / 2) * b.Box(t, d, h)
    if face == "right":
        return b.Pos(w / 2 - t / 2, 0, h / 2) * b.Box(t, d, h)
    if face == "top":
        return b.Pos(0, 0, h - t / 2) * b.Box(w, d, t)
    # bottom: the floor slab
    return b.Pos(0, 0, f / 2) * b.Box(w, d, f)


def _axis_faces(shape: Any, axis: Any, sign: float) -> list[Any]:
    """Planar faces whose normal is within 1 degree of sign*axis."""
    b = build123d()
    result: list[Any] = []
    for face in shape.faces().filter_by(axis):
        if face.geom_type != b.GeomType.PLANE:
            continue
        normal = face.normal_at()
        dot = (
            normal.X * axis.direction.X + normal.Y * axis.direction.Y + normal.Z * axis.direction.Z
        )
        if dot * sign > _AXIS_DOT_TOL:
            result.append(face)
    return result


def _dominant_faces(faces: list[Any]) -> list[Any]:
    """Faces with at least 5% of the group's largest face area."""
    if not faces:
        return []
    largest = max(face.area for face in faces)
    return [face for face in faces if face.area >= largest * 0.05]


def _wall_thickness_checks(brief: DesignBrief, design: GeneratedDesign) -> list[GateCheck]:
    """Min distance between opposing outer/inner faces, per part."""
    b = build123d()
    if brief.design_type == "spur_gear":
        return []
    axes = (b.Axis.X, b.Axis.Y, b.Axis.Z)
    checks: list[GateCheck] = []
    for part in design.parts:
        walls: list[float] = []
        for axis in axes:
            for sign in (1.0, -1.0):
                outer = _axis_faces(part.shape, axis, sign)
                inner = _axis_faces(part.shape, axis, -sign)
                # Small feature faces (welded-in caps, ribs, snap beams) sit
                # ~0.1 mm behind the real wall faces and would otherwise make
                # the minimum a fabrication artifact. Keep only faces whose
                # area is at least 5% of the group's largest.
                outer = _dominant_faces(outer)
                inner = _dominant_faces(inner)
                if not outer or not inner:
                    continue
                distances = [
                    outer_face.distance(inner_face) for outer_face in outer for inner_face in inner
                ]
                if distances:
                    walls.append(min(distances))
        if not walls:
            checks.append(
                GateCheck(
                    "wall_thickness",
                    part.part_id,
                    "unknown",
                    detail="no opposing planar face pairs found",
                )
            )
            continue
        measured = min(walls)
        checks.append(
            GateCheck(
                "wall_thickness",
                part.part_id,
                "pass",
                measured=round(measured, 4),
                detail="minimum opposing-face distance",
            )
        )
    return checks


# --- parametric rule checks -------------------------------------------------


def _parametric_checks(brief: DesignBrief, measured_min_wall_mm: float | None) -> list[GateCheck]:
    checks: list[GateCheck] = []
    dfm_findings = dfm_rules.check_dfm(
        brief, measured_min_wall_mm=measured_min_wall_mm
    ) + dfm_rules.check_standoff_bosses(brief)
    for finding in dfm_findings:
        checks.append(
            GateCheck(
                f"dfm.{finding.rule_id}",
                finding.feature_id or brief.name,
                finding.status,
                measured=finding.measured,
                limit=finding.limit,
                detail=finding.message,
            )
        )
    for finding in mech_rules.check_mechanism_features(brief):
        checks.append(
            GateCheck(
                f"mechanism.{finding.rule_id}",
                f"{finding.feature_id}/{finding.feature_type}",
                finding.status,
                measured=finding.measured,
                limit=finding.limit,
                detail=finding.message,
            )
        )
    for finding in mech_rules.check_gear_rules(brief):
        checks.append(
            GateCheck(
                f"gear.{finding.rule_id}",
                finding.feature_id,
                finding.status,
                measured=finding.measured,
                limit=finding.limit,
                detail=finding.message,
            )
        )
    for declaration in brief.fits:
        result = fits_rules.evaluate_fit(
            declaration.nominal_mm,
            declaration.hole_class,
            declaration.shaft_class,
            declaration.intent,
        )
        checks.append(
            GateCheck(
                "fits",
                declaration.id,
                "pass"
                if result.status == "known" and result.classification == declaration.intent
                else "fail"
                if result.status == "known"
                else "unknown",
                measured=result.min_clearance_mm,
                detail=(
                    f"{declaration.hole_class}/{declaration.shaft_class} "
                    f"({result.min_clearance_mm:+.4f}..{result.max_clearance_mm:+.4f} mm) "
                    f"classified {result.classification}, expected {declaration.intent}"
                ),
            )
        )
    for chain in brief.stackups:
        result = stackup_rules.evaluate_chain(chain)
        checks.append(
            GateCheck(
                "stackup",
                chain.id,
                result.status,
                measured=result.worst_max_mm,
                limit=chain.max_mm,
                detail=(
                    f"worst [{result.worst_min_mm:.4f},{result.worst_max_mm:.4f}] "
                    f"rss {result.rss_mm:.4f}; " + "; ".join(result.reasons)
                ).strip("; "),
            )
        )
    return checks


# --- manifest ---------------------------------------------------------------


def _manifest_checks(out_dir: Path) -> list[GateCheck]:
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        return [GateCheck("manifest", "manifest.json", "unknown", detail="missing")]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [GateCheck("manifest", "manifest.json", "unknown", detail=str(exc))]
    checks: list[GateCheck] = []
    for entry in manifest.get("files", []):
        name = entry["path"]
        path = out_dir / name
        if not path.exists():
            checks.append(GateCheck("manifest", name, "fail", detail="file missing"))
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checks.append(
            GateCheck(
                "manifest",
                name,
                "pass" if digest == entry["sha256"] else "fail",
                detail="sha256 match" if digest == entry["sha256"] else "sha256 mismatch",
            )
        )
    return checks


def run_gates(
    brief: DesignBrief,
    design: GeneratedDesign,
    out_dir: Path,
    *,
    include_artifacts: bool = True,
    board_geometry_path: Path | None = None,
) -> GateReport:
    checks: list[GateCheck] = []
    checks += _kernel_checks(design)
    checks += _interference_checks(design)
    checks += _board_envelope_checks(brief)
    checks += _board_geometry_checks(brief, board_geometry_path)
    checks += _harness_anchor_checks(brief, design)
    checks += _opening_checks(brief, design)
    wall_checks = _wall_thickness_checks(brief, design)
    checks += wall_checks
    measured_walls = [
        c.measured for c in wall_checks if c.measured is not None and c.status == "pass"
    ]
    checks += _parametric_checks(brief, min(measured_walls) if measured_walls else None)
    if include_artifacts:
        checks += _reload_checks(design, out_dir, brief.name)
        checks += _mesh_checks(design, out_dir, brief.name)
        checks += _manifest_checks(out_dir)
    return _aggregate(checks)


__all__ = ["GateCheck", "GateReport", "run_gates"]
