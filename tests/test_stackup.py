from __future__ import annotations

from typing import Any

from mech.brief import StackupChain
from mech.stackup import evaluate_chain


def _chain(max_mm: float, elements: list[dict[str, Any]]) -> StackupChain:
    return StackupChain.model_validate(
        {"id": "SC1", "min_mm": 0.0, "max_mm": max_mm, "elements": elements}
    )


def test_worst_case_math():
    chain = _chain(
        0.5,
        [
            {"name": "a", "nominal_mm": 2.0, "plus_mm": 0.1, "minus_mm": 0.1},
            {"name": "b", "nominal_mm": 0.3, "plus_mm": 0.05, "minus_mm": 0.15},
        ],
    )
    result = evaluate_chain(chain)
    assert abs(result.worst_max_mm - 2.45) < 1e-6
    assert abs(result.worst_min_mm - 2.05) < 1e-6
    assert result.status == "fail"


def test_within_window_passes():
    chain = _chain(
        0.7,
        [
            {"name": "a", "nominal_mm": 1.0, "plus_mm": 0.1, "minus_mm": 0.1},
            {"name": "b", "nominal_mm": -0.5, "plus_mm": 0.05, "minus_mm": 0.05},
        ],
    )
    result = evaluate_chain(chain)
    assert result.status == "pass"


def test_rss_smaller_than_worst():
    chain = _chain(
        10.0,
        [
            {"name": "a", "nominal_mm": 1.0, "plus_mm": 0.1, "minus_mm": 0.1},
            {"name": "b", "nominal_mm": 1.0, "plus_mm": 0.1, "minus_mm": 0.1},
        ],
    )
    result = evaluate_chain(chain)
    assert result.rss_mm < result.worst_max_mm - result.worst_min_mm


def test_empty_chain_rejected():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _chain(1.0, [])
