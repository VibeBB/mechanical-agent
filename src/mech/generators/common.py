"""Shared generator types and a lazy build123d import.

build123d is only needed on the authoring path; importing it lazily keeps the
schema modules (brief/intake) importable without the OCP kernel installed.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any


def build123d() -> Any:
    return importlib.import_module("build123d")


@dataclass(frozen=True)
class GeneratedPart:
    """One manufacturable part of a design."""

    part_id: str
    shape: Any  # build123d Solid/Compound


@dataclass(frozen=True)
class ReferenceSolid:
    """A non-manufacturable solid used by gates (e.g. a board keepout)."""

    reference_id: str
    shape: Any


@dataclass
class GeneratedDesign:
    """Generator output: parts, reference solids, and provenance parameters."""

    parts: list[GeneratedPart]
    references: list[ReferenceSolid] = field(default_factory=list[ReferenceSolid])
    provenance: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass(frozen=True)
class BBox:
    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float

    @property
    def size(self) -> tuple[float, float, float]:
        return (
            self.xmax - self.xmin,
            self.ymax - self.ymin,
            self.zmax - self.zmin,
        )


def shape_bbox(shape: Any) -> BBox:
    box = shape.bounding_box()
    return BBox(
        xmin=float(box.min.X),
        ymin=float(box.min.Y),
        zmin=float(box.min.Z),
        xmax=float(box.max.X),
        ymax=float(box.max.Y),
        zmax=float(box.max.Z),
    )
