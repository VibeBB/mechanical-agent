"""Deterministic engineering data tables.

All values are in millimetres unless noted. The tables are intentionally small
and cover the common ranges the generators and gates need; missing entries
resolve to ``unknown``/fail-closed behaviour rather than extrapolation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialSpec:
    """Mechanical and process properties of a design material."""

    key: str
    name: str
    allowable_strain: float  # strain limit for flexing features (snap fits)
    living_hinge_max_mm: float | None  # max web thickness for a living hinge
    min_bend_radius_factor: float  # min sheet-metal inside bend radius / thickness
    notes: str = ""


# Allowable strain values are conservative, commonly published design limits
# for unfilled grades (cantilever snap-fit design guides).
MATERIALS: dict[str, MaterialSpec] = {
    "PLA": MaterialSpec("PLA", "Polylactic acid", 0.012, None, 0.0, "brittle; avoid snap fits"),
    "ABS": MaterialSpec("ABS", "Acrylonitrile butadiene styrene", 0.03, None, 1.5),
    "ASA": MaterialSpec("ASA", "Acrylonitrile styrene acrylate", 0.03, None, 1.5),
    "PETG": MaterialSpec("PETG", "Polyethylene terephthalate glycol", 0.02, None, 1.0),
    "PA": MaterialSpec("PA", "Polyamide (nylon)", 0.05, 0.5, 1.0, "living-hinge capable"),
    "PP": MaterialSpec("PP", "Polypropylene", 0.06, 0.4, 1.0, "preferred living-hinge resin"),
    "PC": MaterialSpec("PC", "Polycarbonate", 0.015, None, 2.0),
    "AL6061": MaterialSpec("AL6061", "Aluminium 6061", 0.005, None, 0.5),
    "SUS304": MaterialSpec("SUS304", "Stainless steel 304", 0.002, None, 1.0),
}

MATERIAL_KEYS: tuple[str, ...] = tuple(sorted(MATERIALS))


@dataclass(frozen=True)
class ProcessLimits:
    """Fail-closed manufacturing-process rule limits."""

    key: str
    min_wall_mm: float
    max_wall_mm: float  # for uniform-wall processes; 0 disables the check
    min_hole_diameter_mm: float
    min_feature_mm: float
    min_draft_deg: float
    max_overhang_deg: float  # self-supporting overhang angle from vertical; 180 = any
    min_internal_fillet_mm: float
    rib_wall_ratio_max: float  # max rib thickness as a fraction of adjacent wall
    hole_edge_distance_factor: float  # min hole centre to edge distance / diameter
    bend_radius_factor: float  # min inside bend radius / sheet thickness
    hole_to_bend_factor: float  # min hole centre to bend line / thickness


PROCESS_LIMITS: dict[str, ProcessLimits] = {
    "fdm": ProcessLimits(
        key="fdm",
        min_wall_mm=0.8,
        max_wall_mm=0.0,
        min_hole_diameter_mm=1.5,
        min_feature_mm=0.5,
        min_draft_deg=0.0,
        max_overhang_deg=45.0,
        min_internal_fillet_mm=0.0,
        rib_wall_ratio_max=1.0,
        hole_edge_distance_factor=1.0,
        bend_radius_factor=0.0,
        hole_to_bend_factor=0.0,
    ),
    "machining": ProcessLimits(
        key="machining",
        min_wall_mm=0.5,
        max_wall_mm=0.0,
        min_hole_diameter_mm=0.5,
        min_feature_mm=0.8,
        min_draft_deg=0.0,
        max_overhang_deg=180.0,
        min_internal_fillet_mm=0.5,
        rib_wall_ratio_max=1.0,
        hole_edge_distance_factor=1.0,
        bend_radius_factor=0.0,
        hole_to_bend_factor=0.0,
    ),
    "molding": ProcessLimits(
        key="molding",
        min_wall_mm=1.2,
        max_wall_mm=4.0,
        min_hole_diameter_mm=1.0,
        min_feature_mm=0.8,
        min_draft_deg=1.0,
        max_overhang_deg=180.0,
        min_internal_fillet_mm=0.25,
        rib_wall_ratio_max=0.6,
        hole_edge_distance_factor=1.5,
        bend_radius_factor=0.0,
        hole_to_bend_factor=0.0,
    ),
    "sheet_metal": ProcessLimits(
        key="sheet_metal",
        min_wall_mm=0.5,
        max_wall_mm=0.0,
        min_hole_diameter_mm=0.0,  # replaced by 1.0 * thickness
        min_feature_mm=0.0,
        min_draft_deg=0.0,
        max_overhang_deg=180.0,
        min_internal_fillet_mm=0.0,
        rib_wall_ratio_max=1.0,
        hole_edge_distance_factor=1.0,
        bend_radius_factor=1.0,
        hole_to_bend_factor=2.5,
    ),
}

PROCESS_KEYS: tuple[str, ...] = tuple(sorted(PROCESS_LIMITS))


@dataclass(frozen=True)
class ThreadSpec:
    """ISO metric thread data (coarse pitch, tap drill, clearance drills)."""

    designation: str
    pitch_coarse_mm: float
    pitch_fine_mm: float | None
    minor_diameter_mm: float  # internal thread minor diameter (tap drill)
    clearance_close_mm: float  # H13 close fit clearance hole
    clearance_medium_mm: float  # H12 medium fit
    clearance_free_mm: float  # H11 free fit


# ISO 724 / ISO 273 tabulated values.
ISO_METRIC_THREADS: dict[str, ThreadSpec] = {
    "M2": ThreadSpec("M2", 0.4, 0.25, 1.6, 2.2, 2.4, 2.6),
    "M2.5": ThreadSpec("M2.5", 0.45, 0.35, 2.05, 2.7, 2.9, 3.1),
    "M3": ThreadSpec("M3", 0.5, 0.35, 2.5, 3.2, 3.4, 3.6),
    "M4": ThreadSpec("M4", 0.7, 0.5, 3.3, 4.3, 4.5, 4.8),
    "M5": ThreadSpec("M5", 0.8, 0.5, 4.2, 5.3, 5.5, 5.8),
    "M6": ThreadSpec("M6", 1.0, 0.75, 5.0, 6.4, 6.6, 7.0),
    "M8": ThreadSpec("M8", 1.25, 1.0, 6.8, 8.4, 9.0, 10.0),
    "M10": ThreadSpec("M10", 1.5, 1.25, 8.5, 10.5, 11.0, 12.0),
    "M12": ThreadSpec("M12", 1.75, 1.5, 10.2, 13.0, 14.0, 15.0),
}

THREAD_KEYS: tuple[str, ...] = tuple(sorted(ISO_METRIC_THREADS))

# Common bearing seat outer diameters for the seat-fit gate (62xx series).
BEARING_SEATS: dict[str, dict[str, float]] = {
    "608": {"bore_mm": 8.0, "outer_mm": 22.0, "width_mm": 7.0},
    "624": {"bore_mm": 4.0, "outer_mm": 13.0, "width_mm": 5.0},
    "625": {"bore_mm": 5.0, "outer_mm": 16.0, "width_mm": 5.0},
    "626": {"bore_mm": 6.0, "outer_mm": 19.0, "width_mm": 6.0},
    "6200": {"bore_mm": 10.0, "outer_mm": 30.0, "width_mm": 9.0},
    "6201": {"bore_mm": 12.0, "outer_mm": 32.0, "width_mm": 10.0},
    "6202": {"bore_mm": 15.0, "outer_mm": 35.0, "width_mm": 11.0},
    "6203": {"bore_mm": 17.0, "outer_mm": 40.0, "width_mm": 12.0},
    "6204": {"bore_mm": 20.0, "outer_mm": 47.0, "width_mm": 14.0},
}


def material(key: str) -> MaterialSpec:
    spec = MATERIALS.get(key.upper())
    if spec is None:
        raise KeyError(f"unknown material: {key}")
    return spec


def process_limits(key: str) -> ProcessLimits:
    limits = PROCESS_LIMITS.get(key)
    if limits is None:
        raise KeyError(f"unknown process: {key}")
    return limits


def thread(designation: str) -> ThreadSpec:
    spec = ISO_METRIC_THREADS.get(designation.upper())
    if spec is None:
        raise KeyError(f"unknown thread: {designation}")
    return spec
