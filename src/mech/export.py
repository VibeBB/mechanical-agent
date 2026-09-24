"""Deterministic artifact export.

Writes the assembly STEP (all parts in assembly position), per-part STL and
DXF, a single 3MF containing every part, the board-keepout STEP when present,
plus manifest.json (sha256 per file) and provenance.json (generator params and
tool versions). Nothing here judges the design; gates read these artifacts.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import uuid
from pathlib import Path
from typing import Any

from . import dxf_annotate, dxf_lint
from .brief import DesignBrief, brief_sha256
from .generators.common import GeneratedDesign, build123d

_SLICE_THICKNESS_MM = 0.02
_STL_LINEAR_DEFLECTION_MM = 0.1
_STEP_TIMESTAMP_PATTERN = re.compile(r"'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'")
_STEP_EPOCH = "'1970-01-01T00:00:00'"
# OCCT emits a volatile ordinal as the first argument of each NAUO entity.
_STEP_NAUO_PATTERN = re.compile(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\('\d+'")
# build123d's 3MF writer mints a fresh p:UUID per object/build item.
_3MF_UUID_PATTERN = re.compile(r'p:UUID="[0-9a-fA-F-]{36}"')
_3MF_NIL_UUID = 'p:UUID="00000000-0000-4000-8000-000000000000"'


def _normalize_step(path: Path) -> None:
    """Pin volatile STEP fields so exports are byte-reproducible."""
    text = path.read_text(encoding="utf-8")
    text = _STEP_TIMESTAMP_PATTERN.sub(_STEP_EPOCH, text)
    text = _STEP_NAUO_PATTERN.sub("NEXT_ASSEMBLY_USAGE_OCCURRENCE('0'", text)
    path.write_text(text, encoding="utf-8")


def _normalize_3mf(path: Path) -> None:
    """Pin volatile 3MF model XML fields so exports are byte-reproducible."""
    import zipfile

    entries: list[tuple[zipfile.ZipInfo, bytes]] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            entries.append((info, archive.read(info.filename)))
    normalized = path.with_suffix(".normalized")
    with zipfile.ZipFile(normalized, "w", zipfile.ZIP_STORED) as archive:
        for info, data in entries:
            info.compress_type = zipfile.ZIP_STORED
            if info.filename.endswith(".model"):
                data = _3MF_UUID_PATTERN.sub(_3MF_NIL_UUID, data.decode("utf-8")).encode("utf-8")
            archive.writestr(info, data)
    normalized.replace(path)


def _slice_z(brief: DesignBrief, part_id: str) -> float:
    """Representative section height for the 2D outline of each part."""
    spec = brief.enclosure
    if spec is not None:
        if part_id == "lid":
            return spec.height_mm - spec.wall_mm / 2
        return spec.floor_mm + spec.wall_mm / 2
    if brief.bracket is not None:
        return brief.bracket.thickness_mm / 2
    if brief.spur_gear is not None:
        return brief.spur_gear.thickness_mm / 2
    return 0.0


def _top_outline(shape: Any, z_mm: float) -> Any | None:
    """Largest-area XY-planar face of a thin slice at z_mm, flattened to Z=0."""
    b = build123d()
    slab = b.Pos(0, 0, z_mm) * b.Box(1e6, 1e6, _SLICE_THICKNESS_MM)
    try:
        sliced = shape & slab
    except Exception:
        return None
    faces = sliced.faces().filter_by(b.Plane.XY)
    if len(faces) == 0:
        return None
    # Deterministic pick: highest Z, then largest area among coplanar ties.
    top = max(faces, key=lambda f: (round(f.center().Z, 6), f.area))
    return top.moved(b.Pos(0, 0, -top.center().Z))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_design(
    brief: DesignBrief,
    design: GeneratedDesign,
    out_dir: Path,
) -> dict[str, Any]:
    """Write all artifacts; returns the manifest dict."""
    b = build123d()
    out_dir.mkdir(parents=True, exist_ok=True)
    name = brief.name
    files: list[dict[str, Any]] = []

    def record(path: Path, kind: str, part_id: str | None) -> None:
        files.append(
            {
                "path": path.name,
                "kind": kind,
                "part_id": part_id,
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )

    assembly = b.Compound(children=[part.shape for part in design.parts])
    step_path = out_dir / f"{name}.step"
    b.export_step(assembly, str(step_path))
    _normalize_step(step_path)
    record(step_path, "step", None)

    for reference in design.references:
        ref_path = out_dir / f"{name}-{reference.reference_id}.step"
        b.export_step(b.Compound(children=[reference.shape]), str(ref_path))
        _normalize_step(ref_path)
        record(ref_path, "step", reference.reference_id)

    for part in design.parts:
        part_step = out_dir / f"{name}-{part.part_id}.step"
        b.export_step(b.Compound(children=[part.shape]), str(part_step))
        _normalize_step(part_step)
        record(part_step, "step", part.part_id)

        stl_path = out_dir / f"{name}-{part.part_id}.stl"
        b.export_stl(b.Compound(children=[part.shape]), str(stl_path))
        record(stl_path, "stl", part.part_id)

        outline = _top_outline(part.shape, _slice_z(brief, part.part_id))
        if outline is not None:
            dxf_path = out_dir / f"{name}-{part.part_id}.dxf"
            exporter = b.ExportDXF()
            exporter.add_shape(outline)
            exporter.write(str(dxf_path))
            dxf_annotate.annotate_dxf(
                dxf_path,
                design=name,
                part_id=part.part_id,
                material=brief.material,
                process=brief.process,
                fits=brief.fits,
                enclosure=brief.enclosure,
            )
            record(dxf_path, "dxf", part.part_id)
            lint_report = dxf_lint.lint_text(
                dxf_path.read_text(encoding="utf-8", errors="replace"),
                source=Path(dxf_path.name),
            )
            lint_out = lint_report.model_dump_json(indent=2) + "\n"
            lint_path = out_dir / f"{dxf_path.name}_lint.json"
            lint_path.write_text(lint_out, encoding="utf-8")
            record(lint_path, "dxf_lint", part.part_id)

    mesher = b.Mesher()
    for part in design.parts:
        mesher.add_shape(
            b.Compound(children=[part.shape]),
            linear_deflection=_STL_LINEAR_DEFLECTION_MM,
            part_number=part.part_id,
            uuid_value=uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"mech/{brief_sha256(brief)}/{part.part_id}",
            ),
        )
    threemf_path = out_dir / f"{name}.3mf"
    mesher.write(str(threemf_path))
    _normalize_3mf(threemf_path)
    record(threemf_path, "3mf", None)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "design": name,
        "files": files,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    record(manifest_path, "manifest", None)

    ocp_version = "unknown"
    try:
        import OCP  # type: ignore[import-not-found]

        ocp_version = getattr(OCP, "__version__", "unknown")
    except ImportError:
        pass

    provenance = {
        "schema_version": 1,
        "license": "BSD-3-Clause",
        "design": name,
        "brief_sha256": brief_sha256(brief),
        "generator": design.provenance,
        "tools": {
            "python": platform.python_version(),
            "build123d": getattr(b, "__version__", "unknown"),
            "ocp": ocp_version,
        },
    }
    provenance_path = out_dir / "provenance.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    record(provenance_path, "provenance", None)

    return manifest
