"""Linear tolerance stack-up evaluation (worst case and RSS)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .brief import StackupChain


@dataclass(frozen=True)
class StackupResult:
    """Evaluated tolerance chain."""

    chain_id: str
    nominal_mm: float
    worst_min_mm: float
    worst_max_mm: float
    rss_mm: float  # symmetric RSS tolerance about nominal
    status: Literal["pass", "fail"]
    reasons: list[str]


def evaluate_chain(chain: StackupChain) -> StackupResult:
    """Compute worst-case and RSS windows and check the requirement."""
    nominal = sum(element.nominal_mm for element in chain.elements)
    worst_min = nominal - sum(element.minus_mm for element in chain.elements)
    worst_max = nominal + sum(element.plus_mm for element in chain.elements)
    # RSS around nominal: root-sum-square of the half-tolerance of each element.
    rss = math.sqrt(
        sum(((element.plus_mm + element.minus_mm) / 2) ** 2 for element in chain.elements)
    )
    reasons: list[str] = []
    if worst_min < chain.min_mm:
        reasons.append(f"worst-case minimum {worst_min:.4f} below {chain.min_mm:.4f}")
    if worst_max > chain.max_mm:
        reasons.append(f"worst-case maximum {worst_max:.4f} above {chain.max_mm:.4f}")
    return StackupResult(
        chain_id=chain.id,
        nominal_mm=nominal,
        worst_min_mm=worst_min,
        worst_max_mm=worst_max,
        rss_mm=rss,
        status="fail" if reasons else "pass",
        reasons=reasons,
    )
