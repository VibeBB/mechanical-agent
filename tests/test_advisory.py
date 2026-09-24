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
            "findings": [
                {
                    "category": "text_collision",
                    "severity": "warning",
                    "note": "dimension text overlaps hatch region",
                    "bbox": [0.1, 0.2, 0.05, 0.03],
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
    assert len(detail.findings) == 2
    assert detail.findings[0].bbox == [0.1, 0.2, 0.05, 0.03]


def test_parse_visual_review_rejects_non_vision_tool() -> None:
    result = _vision_result()
    result.tool = "mech_gates"
    assert parse_visual_review(result) is None


def test_parse_visual_review_rejects_malformed_detail() -> None:
    result = _vision_result()
    result.detail = {"image_path": "x.png", "image_sha256": "not-a-hash"}
    assert parse_visual_review(result) is None


def test_visual_review_detail_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        VisualReviewDetail.model_validate(
            {
                "image_path": "x.png",
                "image_sha256": "a" * 64,
                "model": "m",
                "checklist": "dxf_outline",
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
                "findings": [{"category": "silkscreen_overlap", "severity": "info", "note": "x"}],
            }
        )
