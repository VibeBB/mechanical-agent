"""Machine-readable design brief models and helpers.

The brief is the single source of truth for a design. Every artifact is a
projection of these bytes; nothing flows back into the brief.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .standards import MATERIAL_KEYS, PROCESS_KEYS, THREAD_KEYS

SIDE_FACES: tuple[str, ...] = ("front", "back", "left", "right")
ALL_FACES: tuple[str, ...] = (*SIDE_FACES, "top", "bottom")


class Opening(BaseModel):
    """A hole through an enclosure wall.

    ``center_x_mm``/``center_y_mm`` are face-local coordinates with the origin
    at the face centre: x runs along the face width (or depth on top/bottom),
    y along the enclosure height (or depth on top/bottom).
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^O[0-9]+$")
    face: Literal["front", "back", "left", "right", "top", "bottom"]
    kind: Literal["rect", "round"] = "rect"
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    center_x_mm: float = 0.0
    center_y_mm: float = 0.0

    @model_validator(mode="after")
    def validate_shape(self) -> Opening:
        if self.kind == "round" and self.width_mm != self.height_mm:
            raise ValueError("round openings require width_mm == height_mm")
        return self


class MountHole(BaseModel):
    """Board mounting hole in board-local coordinates (origin: board centre)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^MH[0-9]+$")
    x_mm: float
    y_mm: float
    diameter_mm: float = Field(gt=0)


class BoardSpec(BaseModel):
    """Internal PCB that the enclosure must clear."""

    model_config = ConfigDict(extra="forbid")

    width_mm: float = Field(gt=0)
    depth_mm: float = Field(gt=0)
    thickness_mm: float = Field(gt=0, default=1.6)
    keepout_height_mm: float = Field(ge=0, default=0.0)
    mount_holes: list[MountHole] = Field(default_factory=list[MountHole])


class VentSpec(BaseModel):
    """Slot grid milled through a wall for ventilation."""

    model_config = ConfigDict(extra="forbid")

    face: Literal["top", "front", "back", "left", "right"] = "top"
    slot_width_mm: float = Field(gt=0)
    slot_length_mm: float = Field(gt=0)
    slot_pitch_mm: float = Field(gt=0)
    margin_mm: float = Field(ge=0, default=4.0)


class LidScrew(BaseModel):
    """Screw fastening for a removable lid."""

    model_config = ConfigDict(extra="forbid")

    size: str
    boss_diameter_mm: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_thread(self) -> LidScrew:
        if self.size.upper() not in THREAD_KEYS:
            raise ValueError(f"unsupported thread size: {self.size}")
        return self


class EnclosureSpec(BaseModel):
    """Two-piece clamshell enclosure around an optional internal board."""

    model_config = ConfigDict(extra="forbid")

    width_mm: float = Field(gt=0)  # outer envelope X
    depth_mm: float = Field(gt=0)  # outer envelope Y
    height_mm: float = Field(gt=0)  # outer envelope Z
    wall_mm: float = Field(gt=0)
    floor_mm: float = Field(gt=0)
    lid: Literal["screw", "snap"] = "screw"
    corner_radius_mm: float = Field(ge=0, default=0.0)
    clearance_mm: float = Field(gt=0)  # board-to-inner-wall gap
    standoff_height_mm: float = Field(gt=0)
    board: BoardSpec | None = None
    openings: list[Opening] = Field(default_factory=list[Opening])
    vent: VentSpec | None = None
    screw: LidScrew | None = None

    @model_validator(mode="after")
    def validate_geometry(self) -> EnclosureSpec:
        if 2 * self.wall_mm >= min(self.width_mm, self.depth_mm):
            raise ValueError("wall_mm leaves no interior cavity")
        if 2 * self.corner_radius_mm > min(self.width_mm, self.depth_mm):
            raise ValueError("corner_radius_mm exceeds half the smaller envelope side")
        if self.lid == "screw" and self.screw is None:
            raise ValueError("lid='screw' requires a screw spec")
        if self.board is not None:
            board = self.board
            cavity_w = self.width_mm - 2 * self.wall_mm - 2 * self.clearance_mm
            cavity_d = self.depth_mm - 2 * self.wall_mm - 2 * self.clearance_mm
            if board.width_mm > cavity_w or board.depth_mm > cavity_d:
                raise ValueError("board does not fit the interior cavity with clearance")
            for hole in board.mount_holes:
                if not (
                    -board.width_mm / 2 <= hole.x_mm <= board.width_mm / 2
                    and -board.depth_mm / 2 <= hole.y_mm <= board.depth_mm / 2
                ):
                    raise ValueError(f"mount hole {hole.id} is outside the board")
        for opening in self.openings:
            face_w, face_h = face_span(self, opening.face)
            if abs(opening.center_x_mm) + opening.width_mm / 2 > face_w / 2:
                raise ValueError(f"opening {opening.id} exceeds face {opening.face} width")
            if abs(opening.center_y_mm) + opening.height_mm / 2 > face_h / 2:
                raise ValueError(f"opening {opening.id} exceeds face {opening.face} height")
        ids = [opening.id for opening in self.openings]
        if len(set(ids)) != len(ids):
            raise ValueError("opening ids must be unique")
        hole_ids = [h.id for h in (self.board.mount_holes if self.board else [])]
        if len(set(hole_ids)) != len(hole_ids):
            raise ValueError("mount hole ids must be unique")
        return self


def face_span(spec: EnclosureSpec, face: str) -> tuple[float, float]:
    """Return (width, height) of a wall face in face-local coordinates."""
    if face in ("front", "back"):
        return spec.width_mm, spec.height_mm
    if face in ("left", "right"):
        return spec.depth_mm, spec.height_mm
    return spec.width_mm, spec.depth_mm


class BracketHole(BaseModel):
    """A drilled hole on one bracket face, face-local coordinates at centre."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^H[0-9]+$")
    face: Literal["base", "leg", "plate"]
    x_mm: float
    y_mm: float
    diameter_mm: float = Field(gt=0)
    depth_mm: float | None = Field(default=None, gt=0)  # None = through
    countersink_diameter_mm: float | None = Field(default=None, gt=0)


class BracketSpec(BaseModel):
    """Plate, L-bracket, or U-bracket with drilled features."""

    model_config = ConfigDict(extra="forbid")

    form: Literal["plate", "l", "u"]
    width_mm: float = Field(gt=0)  # extrusion depth (Y)
    thickness_mm: float = Field(gt=0)
    plate_length_mm: float = Field(gt=0, default=0.0)  # form "plate" X extent
    base_mm: float = Field(gt=0, default=0.0)  # horizontal leg (X)
    leg_mm: float = Field(gt=0, default=0.0)  # vertical leg (Z)
    inner_fillet_mm: float = Field(ge=0, default=0.0)
    gusset: bool = False
    holes: list[BracketHole] = Field(default_factory=list[BracketHole])

    @model_validator(mode="after")
    def validate_geometry(self) -> BracketSpec:
        if self.form == "plate":
            if self.plate_length_mm <= 0:
                raise ValueError("form='plate' requires plate_length_mm")
            if self.gusset:
                raise ValueError("gusset requires a vertical leg")
        else:
            if self.base_mm <= 0 or self.leg_mm <= 0:
                raise ValueError("l/u brackets require base_mm and leg_mm")
            if self.inner_fillet_mm > min(self.base_mm, self.leg_mm) - self.thickness_mm:
                raise ValueError("inner_fillet_mm exceeds the inner corner space")
            if self.gusset and self.form == "u":
                raise ValueError("gusset is only defined for the l bracket")
        ids = [hole.id for hole in self.holes]
        if len(set(ids)) != len(ids):
            raise ValueError("hole ids must be unique")
        for hole in self.holes:
            self._check_hole(hole)
        return self

    def _check_hole(self, hole: BracketHole) -> None:
        if self.form == "plate":
            if hole.face != "plate":
                raise ValueError(f"hole {hole.id} on '{hole.face}' but form is plate")
            span_x, span_y = self.plate_length_mm, self.width_mm
        elif hole.face == "base":
            span_x, span_y = self.base_mm, self.width_mm
        else:
            span_x, span_y = self.leg_mm, self.width_mm
        if abs(hole.x_mm) + hole.diameter_mm / 2 > span_x / 2:
            raise ValueError(f"hole {hole.id} exceeds face {hole.face} span x")
        if abs(hole.y_mm) + hole.diameter_mm / 2 > span_y / 2:
            raise ValueError(f"hole {hole.id} exceeds face {hole.face} span y")
        if hole.countersink_diameter_mm is not None and hole.countersink_diameter_mm <= (
            hole.diameter_mm
        ):
            raise ValueError(f"hole {hole.id} countersink smaller than diameter")


class SpurGearSpec(BaseModel):
    """Metric involute spur gear with optional hub."""

    model_config = ConfigDict(extra="forbid")

    module_mm: float = Field(gt=0)
    teeth: int = Field(ge=8)
    pressure_angle_deg: float = Field(gt=0, le=30, default=20.0)
    thickness_mm: float = Field(gt=0)
    bore_mm: float = Field(gt=0)
    hub_diameter_mm: float = Field(gt=0, default=0.0)  # 0 = no hub
    hub_height_mm: float = Field(gt=0, default=0.0)
    backlash_mm: float = Field(ge=0, default=0.0)

    @model_validator(mode="after")
    def validate_geometry(self) -> SpurGearSpec:
        root_diameter = self.module_mm * (self.teeth - 2.5)
        if self.bore_mm >= root_diameter:
            raise ValueError("bore_mm exceeds the gear root diameter")
        if self.hub_diameter_mm > 0:
            if self.hub_height_mm <= 0:
                raise ValueError("hub_diameter_mm requires hub_height_mm")
            if self.hub_diameter_mm >= root_diameter:
                raise ValueError("hub_diameter_mm exceeds the root diameter")
            if self.hub_diameter_mm <= self.bore_mm:
                raise ValueError("hub_diameter_mm must exceed bore_mm")
        return self


class MechanismFeature(BaseModel):
    """Opt-in mechanism feature attached to the generated part.

    ``mount`` selects the host part: ``shell``/``lid`` for enclosures, and
    ``base``/``leg``/``plate`` for brackets. Modeled types place themselves
    deterministically from ``face``/``x_mm``/``y_mm``/``z_mm``; the remaining
    types are validated parametrically by the mechanism rules.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^F[0-9]+$")
    type: Literal["snap_fit", "living_hinge", "rib", "boss", "detent"]
    mount: str = "shell"
    # placement on the host (enclosure mounts only; see generators/features.py)
    face: Literal["front", "back", "left", "right"] = "front"
    x_mm: float = 0.0  # face-local coordinate along the wall
    y_mm: float = 0.0  # boss placement: floor-local Y
    z_mm: float = 0.0  # height above the inner floor
    # snap_fit (cantilever beam)
    length_mm: float = Field(gt=0, default=0.0)
    hook_thickness_mm: float = Field(gt=0, default=0.0)
    deflection_mm: float = Field(ge=0, default=0.0)
    width_mm: float = Field(gt=0, default=0.0)
    # living_hinge (parametric only)
    web_thickness_mm: float = Field(gt=0, default=0.0)
    # rib / boss / detent
    thickness_mm: float = Field(gt=0, default=0.0)
    height_mm: float = Field(ge=0, default=0.0)
    od_mm: float = Field(gt=0, default=0.0)
    id_mm: float = Field(ge=0, default=0.0)
    ramp_angle_deg: float = Field(gt=0, le=90, default=0.0)
    depth_mm: float = Field(ge=0, default=0.0)


class FitDeclaration(BaseModel):
    """An ISO limits-and-fits requirement on a designed interface."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^FT[0-9]+$")
    feature: str = Field(min_length=1)
    nominal_mm: float = Field(gt=0)
    hole_class: str = Field(pattern=r"^H(6|7|8|10|11)$")
    shaft_class: str = Field(pattern=r"^(e8|f7|g6|h6|h7|h8|k6|n6|p6|s6)$")
    intent: Literal["clearance", "transition", "interference"]


class StackupElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    nominal_mm: float
    plus_mm: float = Field(ge=0)
    minus_mm: float = Field(ge=0)


class StackupChain(BaseModel):
    """A linear 1D tolerance chain checked against a requirement window."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^SC[0-9]+$")
    elements: list[StackupElement] = Field(min_length=1)
    min_mm: float
    max_mm: float

    @model_validator(mode="after")
    def validate_bounds(self) -> StackupChain:
        if self.min_mm >= self.max_mm:
            raise ValueError("min_mm must be less than max_mm")
        names = [element.name for element in self.elements]
        if len(set(names)) != len(names):
            raise ValueError("element names must be unique")
        return self


class HarnessAnchor(BaseModel):
    """A fixturing point exported to wire-agent as an envelope anchor.

    `kind` names the seat type (clip, grommet, breakout, other);
    `position_mm` is the anchor's location in the design coordinate
    frame when known.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    kind: Literal["clip", "grommet", "breakout", "other"] = "other"
    position_mm: tuple[float, float, float] | None = None


class DesignBrief(BaseModel):
    """Top-level design contract consumed by the generators and gates."""

    model_config = ConfigDict(extra="forbid")

    id_pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Z]+[0-9]+$")

    name: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    description: str = ""
    design_type: Literal["enclosure", "bracket", "spur_gear"]
    material: str
    process: Literal["fdm", "machining", "molding", "sheet_metal"]
    enclosure: EnclosureSpec | None = None
    bracket: BracketSpec | None = None
    spur_gear: SpurGearSpec | None = None
    mechanism_features: list[MechanismFeature] = Field(default_factory=list[MechanismFeature])
    fits: list[FitDeclaration] = Field(default_factory=list[FitDeclaration])
    stackups: list[StackupChain] = Field(default_factory=list[StackupChain])
    harness_anchors: list[HarnessAnchor] = Field(default_factory=list[HarnessAnchor])

    @model_validator(mode="after")
    def validate_design(self) -> DesignBrief:
        if self.material.upper() not in MATERIAL_KEYS:
            raise ValueError(f"unsupported material: {self.material}")
        if self.process not in PROCESS_KEYS:
            raise ValueError(f"unsupported process: {self.process}")
        spec = getattr(self, self.design_type)
        if spec is None:
            raise ValueError(f"design_type={self.design_type} requires its spec block")
        others = {
            "enclosure": self.enclosure,
            "bracket": self.bracket,
            "spur_gear": self.spur_gear,
        }
        for key, value in others.items():
            if key != self.design_type and value is not None:
                raise ValueError(f"{key} spec must be null for design_type={self.design_type}")
        if self.design_type == "spur_gear" and self.mechanism_features:
            raise ValueError("spur_gear does not accept mechanism features")
        feature_ids = [feature.id for feature in self.mechanism_features]
        if len(set(feature_ids)) != len(feature_ids):
            raise ValueError("mechanism feature ids must be unique")
        declared = set(feature_ids)
        for fit in self.fits:
            if fit.feature not in declared and not _feature_id_known(self, fit.feature):
                raise ValueError(f"fit {fit.id} references unknown feature: {fit.feature}")
        anchor_names = [anchor.name for anchor in self.harness_anchors]
        if len(set(anchor_names)) != len(anchor_names):
            raise ValueError("harness anchor names must be unique")
        return self

    def part_ids(self) -> list[str]:
        """Deterministic ids of the generated parts."""
        if self.design_type == "enclosure":
            return ["shell", "lid"]
        if self.design_type == "bracket":
            return ["bracket"]
        return ["gear"]

    def feature_ids(self) -> list[str]:
        """Deterministic ids of every addressable brief feature."""
        ids: list[str] = []
        if self.enclosure is not None:
            ids.extend(opening.id for opening in self.enclosure.openings)
            if self.enclosure.board is not None:
                ids.extend(hole.id for hole in self.enclosure.board.mount_holes)
        if self.bracket is not None:
            ids.extend(hole.id for hole in self.bracket.holes)
        ids.extend(feature.id for feature in self.mechanism_features)
        ids.extend(fit.id for fit in self.fits)
        ids.extend(chain.id for chain in self.stackups)
        return ids


def _feature_id_known(brief: DesignBrief, feature: str) -> bool:
    known = set(brief.part_ids()) | set(brief.feature_ids())
    return feature in known


def brief_sha256(brief: DesignBrief) -> str:
    """Canonical JSON digest used by the intake sidecar and provenance."""
    payload = brief.model_dump_json()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_brief(path: Path) -> DesignBrief:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load design brief {path}: {exc}") from exc
    return DesignBrief.model_validate(value)
