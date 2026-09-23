"""Deterministic parametric generators keyed by design_type."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..brief import DesignBrief
    from .common import GeneratedDesign


def generate(brief: DesignBrief) -> GeneratedDesign:
    """Dispatch to the design-type generator. Fail-closed on unknown types."""
    if brief.design_type == "enclosure":
        from .enclosure import generate_enclosure

        return generate_enclosure(brief)
    if brief.design_type == "bracket":
        from .bracket import generate_bracket

        return generate_bracket(brief)
    if brief.design_type == "spur_gear":
        from .gear import generate_spur_gear

        return generate_spur_gear(brief)
    raise ValueError(f"unsupported design_type: {brief.design_type}")


__all__ = ["generate"]
