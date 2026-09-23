"""ISO 286 limits-and-fits tables (subset) and clearance evaluation.

Values are micrometres converted to millimetres on return. The table covers
the nominal ranges, tolerance grades, and shaft deviations needed for common
shaft/seat/press-fit work. Ranges or classes outside the table evaluate to
``unknown`` and fail closed at the gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Nominal range upper edges (mm). Index i covers (lower, upper].
NOMINAL_BINS: tuple[tuple[float, float], ...] = (
    (0.0, 3.0),
    (3.0, 6.0),
    (6.0, 10.0),
    (10.0, 18.0),
    (18.0, 30.0),
    (30.0, 50.0),
    (50.0, 65.0),
    (65.0, 80.0),
    (80.0, 100.0),
    (100.0, 120.0),
    (120.0, 140.0),
    (140.0, 160.0),
    (160.0, 180.0),
)

# IT grades in µm per bin.
IT_GRADES: dict[int, tuple[int, ...]] = {
    6: (6, 8, 9, 11, 13, 16, 19, 19, 22, 22, 25, 25, 25),
    7: (10, 12, 15, 18, 21, 25, 30, 30, 35, 35, 40, 40, 40),
    8: (14, 18, 22, 27, 33, 39, 46, 46, 54, 54, 63, 63, 63),
    10: (40, 48, 58, 70, 84, 100, 120, 120, 140, 140, 160, 160, 160),
    11: (60, 75, 90, 110, 130, 160, 190, 190, 220, 220, 250, 250, 250),
}

HOLE_CLASSES: tuple[str, ...] = ("H6", "H7", "H8", "H10", "H11")

# Shaft fundamental deviations. For e/f/g the fundamental deviation is the
# upper deviation es (ei = es - IT); for h es = 0 (ei = -IT); for k/n/p/s the
# fundamental deviation is the lower deviation ei (es = ei + IT).
SHAFT_UPPER_DEVIATION_UM: dict[str, tuple[int, ...]] = {
    "e": (-14, -20, -25, -32, -40, -50, -60, -60, -72, -72, -85, -85, -85),
    "f": (-6, -10, -13, -16, -20, -25, -30, -30, -36, -36, -43, -43, -43),
    "g": (-2, -4, -5, -6, -7, -9, -10, -10, -12, -12, -14, -14, -14),
}
SHAFT_LOWER_DEVIATION_UM: dict[str, tuple[int, ...]] = {
    "k": (0, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3),
    "n": (4, 8, 10, 12, 15, 17, 20, 20, 23, 23, 27, 27, 27),
    "p": (6, 12, 15, 18, 22, 26, 32, 32, 37, 37, 43, 43, 43),
    "s": (14, 19, 23, 28, 35, 43, 53, 59, 71, 79, 92, 100, 108),
}
SHAFT_GRADES: dict[str, int] = {
    "e8": 8,
    "f7": 7,
    "g6": 6,
    "h6": 6,
    "h7": 7,
    "h8": 8,
    "k6": 6,
    "n6": 6,
    "p6": 6,
    "s6": 6,
}
SHAFT_CLASSES: tuple[str, ...] = tuple(sorted(SHAFT_GRADES))

FitIntent = Literal["clearance", "transition", "interference"]


@dataclass(frozen=True)
class LimitsMm:
    """Upper/lower deviations for a nominal size, in millimetres."""

    upper_mm: float
    lower_mm: float


@dataclass(frozen=True)
class FitResult:
    """Evaluated ISO fit between a hole and a shaft."""

    nominal_mm: float
    hole_class: str
    shaft_class: str
    hole: LimitsMm
    shaft: LimitsMm
    max_clearance_mm: float  # positive: clearance; negative: interference
    min_clearance_mm: float
    classification: FitIntent
    status: Literal["known", "unknown"]
    reason: str = ""


def _bin_index(nominal_mm: float) -> int | None:
    if nominal_mm <= 0:
        return None
    for index, (lower, upper) in enumerate(NOMINAL_BINS):
        if lower < nominal_mm <= upper:
            return index
    return None


def hole_limits(hole_class: str, nominal_mm: float) -> LimitsMm | None:
    """Hole-basis limits: lower deviation 0, upper +IT."""
    index = _bin_index(nominal_mm)
    if index is None or len(hole_class) != 2 or hole_class[0] != "H":
        return None
    try:
        grade = int(hole_class[1])
    except ValueError:
        return None
    table = IT_GRADES.get(grade)
    if table is None:
        return None
    return LimitsMm(upper_mm=table[index] / 1000.0, lower_mm=0.0)


def shaft_limits(shaft_class: str, nominal_mm: float) -> LimitsMm | None:
    """Shaft limits for a supported class like ``g6`` or ``s6``."""
    index = _bin_index(nominal_mm)
    grade = SHAFT_GRADES.get(shaft_class)
    if index is None or grade is None:
        return None
    it_mm = IT_GRADES[grade][index] / 1000.0
    letter = shaft_class[0]
    if letter in SHAFT_UPPER_DEVIATION_UM:
        es = SHAFT_UPPER_DEVIATION_UM[letter][index] / 1000.0
        return LimitsMm(upper_mm=es, lower_mm=es - it_mm)
    if letter == "h":
        return LimitsMm(upper_mm=0.0, lower_mm=-it_mm)
    if letter in SHAFT_LOWER_DEVIATION_UM:
        ei = SHAFT_LOWER_DEVIATION_UM[letter][index] / 1000.0
        return LimitsMm(upper_mm=ei + it_mm, lower_mm=ei)
    return None


def evaluate_fit(
    nominal_mm: float,
    hole_class: str,
    shaft_class: str,
    intent: FitIntent,
) -> FitResult:
    """Compute the clearance window and classify it against the intent."""
    hole = hole_limits(hole_class, nominal_mm)
    shaft = shaft_limits(shaft_class, nominal_mm)
    if hole is None or shaft is None:
        return FitResult(
            nominal_mm=nominal_mm,
            hole_class=hole_class,
            shaft_class=shaft_class,
            hole=hole or LimitsMm(0.0, 0.0),
            shaft=shaft or LimitsMm(0.0, 0.0),
            max_clearance_mm=0.0,
            min_clearance_mm=0.0,
            classification="transition",
            status="unknown",
            reason="unsupported nominal size or tolerance class",
        )
    max_clearance = hole.upper_mm - shaft.lower_mm
    min_clearance = hole.lower_mm - shaft.upper_mm
    if min_clearance > 0:
        classification: FitIntent = "clearance"
    elif max_clearance < 0:
        classification = "interference"
    else:
        classification = "transition"
    reason = ""
    if classification != intent:
        reason = f"fit classifies as {classification}, expected {intent}"
    return FitResult(
        nominal_mm=nominal_mm,
        hole_class=hole_class,
        shaft_class=shaft_class,
        hole=hole,
        shaft=shaft,
        max_clearance_mm=max_clearance,
        min_clearance_mm=min_clearance,
        classification=classification,
        status="known",
        reason=reason,
    )
