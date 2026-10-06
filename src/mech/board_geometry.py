"""circuit-agent board geometry import (``*.board-geometry.json``).

A strict mirror of circuit-agent's ``circuit_board_geometry`` contract. The
board frame (origin at the board centre, +y toward the back face) is the
enclosure frame, so a board pinned in ``enclosure.board.source`` is assumed
to sit unrotated on the standoffs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .brief import BoardGeometrySource, DesignBrief
from .workspace import workspace_path

DIMENSION_TOL_MM = 0.05
HOLE_TOL_MM = 0.05
COURTYARD_EXCESS_MM = 0.25

Face = Literal["front", "back", "left", "right"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceFile(_Strict):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class StepModel(SourceFile):
    valid: bool


class GeometryHole(_Strict):
    ref: str
    x_mm: float
    y_mm: float
    diameter_mm: float = Field(gt=0)


class GeometryComponent(_Strict):
    ref: str
    lib_id: str
    side: Literal["top", "bottom"]
    x_mm: float
    y_mm: float
    rotation_deg: float
    bbox_mm: tuple[float, float, float, float] | None
    height_mm: float | None
    height_sources: list[Literal["property", "part_spec", "step_model"]]
    connector: bool
    edge: Face | None


class BoardGeometry(_Strict):
    artifact_kind: Literal["circuit_board_geometry"]
    schema_version: Literal[1]
    frame: Literal["board_center_y_up_mm"]
    pcb: SourceFile
    part_specs: dict[str, str]
    step: StepModel | None
    width_mm: float | None
    depth_mm: float | None
    thickness_mm: float | None
    outline_mm: list[tuple[float, float]]
    mount_holes: list[GeometryHole]
    components: list[GeometryComponent]
    max_height_top_mm: float | None
    max_height_bottom_mm: float | None
    unknown: list[str]
    verdict: Literal["pass", "fail"]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_geometry(path: Path) -> BoardGeometry:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load board geometry {path}: {exc}") from exc
    return BoardGeometry.model_validate(payload)


def resolve_source(brief: DesignBrief, base_dir: Path, *, confine: bool = False) -> Path | None:
    """Path of the pinned geometry; ``confine`` keeps MCP reads inside the workspace."""
    spec = brief.enclosure
    source = spec.board.source if spec is not None and spec.board is not None else None
    if source is None:
        return None
    if confine:
        return workspace_path(source.path, root=base_dir)
    candidate = Path(source.path)
    return candidate if candidate.is_absolute() else base_dir / candidate


def suggest_board(geometry: BoardGeometry, source_path: str, sha256: str) -> dict[str, Any]:
    """BoardSpec block (plus connector opening targets) derived from a geometry."""
    if geometry.verdict != "pass" or geometry.width_mm is None or geometry.depth_mm is None:
        raise ValueError(f"board geometry is not complete: unknown={geometry.unknown}")
    board = {
        "width_mm": geometry.width_mm,
        "depth_mm": geometry.depth_mm,
        "thickness_mm": geometry.thickness_mm,
        "keepout_height_mm": geometry.max_height_top_mm,
        "mount_holes": [
            {"id": f"MH{index}", "x_mm": h.x_mm, "y_mm": h.y_mm, "diameter_mm": h.diameter_mm}
            for index, h in enumerate(geometry.mount_holes, start=1)
        ],
        "source": BoardGeometrySource(path=source_path, sha256=sha256).model_dump(),
    }
    targets = [
        {
            "ref": c.ref,
            "face": c.edge,
            "side": c.side,
            "along_mm": list(along_span(c)),
            "height_mm": c.height_mm,
        }
        for c in geometry.components
        if c.connector and c.edge is not None and c.bbox_mm is not None
    ]
    return {"board": board, "connector_openings": targets}


def along_span(component: GeometryComponent) -> tuple[float, float]:
    """Face-local span of a part's courtyard (minus the IPC courtyard excess)."""
    assert component.bbox_mm is not None
    x0, y0, x1, y1 = component.bbox_mm
    low, high = (x0, x1) if component.edge in ("front", "back") else (y0, y1)
    return round(low + COURTYARD_EXCESS_MM, 4), round(high - COURTYARD_EXCESS_MM, 4)


__all__ = [
    "BoardGeometry",
    "along_span",
    "load_geometry",
    "resolve_source",
    "sha256_file",
    "suggest_board",
]
