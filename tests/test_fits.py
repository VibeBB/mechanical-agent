from __future__ import annotations

from mech.fits import evaluate_fit, hole_limits, shaft_limits


def test_known_clearance_fit():
    result = evaluate_fit(20.0, "H7", "g6", "clearance")
    assert result.status == "known"
    assert result.classification == "clearance"
    assert result.min_clearance_mm > 0


def test_known_interference_fit():
    result = evaluate_fit(20.0, "H7", "p6", "interference")
    assert result.status == "known"
    assert result.max_clearance_mm < 0


def test_intent_mismatch_flagged():
    result = evaluate_fit(20.0, "H7", "g6", "interference")
    assert result.status == "known"
    assert result.classification == "clearance"
    assert "expected" in result.reason


def test_unknown_class_fail_closed():
    result = evaluate_fit(20.0, "H7", "q9", "clearance")
    assert result.status == "unknown"


def test_unknown_nominal_bin():
    result = evaluate_fit(-1.0, "H7", "g6", "clearance")
    assert result.status == "unknown"


def test_hole_limits_sign():
    limits = hole_limits("H7", 20.0)
    assert limits is not None
    assert limits.lower_mm == 0.0
    assert limits.upper_mm > 0


def test_shaft_g6_all_negative():
    limits = shaft_limits("g6", 20.0)
    assert limits is not None
    assert limits.upper_mm < 0


def test_transition_fit():
    result = evaluate_fit(20.0, "H7", "k6", "transition")
    assert result.status == "known"
    assert result.min_clearance_mm <= 0 <= result.max_clearance_mm
