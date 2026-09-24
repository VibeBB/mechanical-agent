import pytest
from pydantic import ValidationError

from mech.advisory import (
    AdvisoryResult,
    VisualReviewDetail,
    parse_visual_review,
)


def _vision_result() -> AdvisoryResult:
    return AdvisoryResult(
        tool="vision_review",
        stage="review",
        status="ok",
        summary="lid outline clean",
        artifacts=["out/demo-lid.png"],
        detail={
            "image_path": "out/demo-lid.png",
            "image_sha256": "a" * 64,
            "model": "kimi-k3",
            "checklist": "dxf_outline",
            "impression": "reads like a buildable sheet; dims anchored to the mating face",
            "findings": [
                {
                    "category": "text_collision",
                    "severity": "warning",
                    "note": "dimension text overlaps hatch region",
                    "bbox": [0.1, 0.2, 0.05, 0.03],
                },
                {
                    "category": "design_intent",
                    "severity": "info",
                    "note": "hole pattern chained off a corner instead of the bore datum",
                },
                {"category": "other", "severity": "info", "note": "sparse right edge"},
            ],
        },
    )


def test_parse_visual_review_round_trip() -> None:
    detail = parse_visual_review(_vision_result())
    assert detail is not None
    assert detail.checklist == "dxf_outline"
    assert detail.model == "kimi-k3"
    assert detail.impression.startswith("reads like a buildable sheet")
    assert len(detail.findings) == 3
    assert detail.findings[0].bbox == [0.1, 0.2, 0.05, 0.03]
    assert detail.findings[1].category == "design_intent"


def test_parse_visual_review_rejects_non_vision_tool() -> None:
    result = _vision_result()
    result.tool = "mech_gates"
    assert parse_visual_review(result) is None


def test_parse_visual_review_rejects_malformed_detail() -> None:
    result = _vision_result()
    result.detail = {"image_path": "x.png", "image_sha256": "not-a-hash"}
    assert parse_visual_review(result) is None


def test_parse_visual_review_requires_impression() -> None:
    result = _vision_result()
    assert result.detail is not None
    del result.detail["impression"]
    assert parse_visual_review(result) is None

    result = _vision_result()
    assert result.detail is not None
    result.detail["impression"] = ""
    assert parse_visual_review(result) is None


def test_visual_review_detail_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        VisualReviewDetail.model_validate(
            {
                "image_path": "x.png",
                "image_sha256": "a" * 64,
                "model": "m",
                "checklist": "dxf_outline",
                "impression": "i",
                "verdict": "fail",
            }
        )


def test_visual_review_detail_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        VisualReviewDetail.model_validate(
            {
                "image_path": "x.png",
                "image_sha256": "a" * 64,
                "model": "m",
                "checklist": "dxf_outline",
                "impression": "i",
                "findings": [{"category": "silkscreen_overlap", "severity": "info", "note": "x"}],
            }
        )


def test_visual_review_detail_accepts_drawing_quality_categories() -> None:
    for category in (
        "ambiguous_notation",
        "missing_dimension",
        "missing_manufacturing_info",
        "design_intent",
    ):
        detail = VisualReviewDetail.model_validate(
            {
                "image_path": "x.png",
                "image_sha256": "a" * 64,
                "model": "m",
                "checklist": "dxf_outline",
                "impression": "reads clearly",
                "findings": [{"category": category, "severity": "info", "note": "x"}],
            }
        )
        assert detail.findings[0].category == category
