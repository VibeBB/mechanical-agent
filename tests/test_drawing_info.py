from __future__ import annotations

import pytest
from pydantic import ValidationError

from mech.brief import DrawingInfo
from mech.dxf_annotate import _title_rows  # pyright: ignore[reportPrivateUsage]


def test_status_is_derived_from_release_fields():
    assert DrawingInfo().status == "In preparation"
    assert DrawingInfo(approved_by="K. Tanaka").status == "In approval"
    released = DrawingInfo(approved_by="K. Tanaka", date_of_issue="2026-10-05")
    assert released.status == "Released"


def test_issue_date_requires_an_approver():
    with pytest.raises(ValidationError, match="requires approved_by"):
        DrawingInfo(date_of_issue="2026-10-05")


def test_issue_date_must_be_a_calendar_date():
    with pytest.raises(ValidationError, match="calendar date"):
        DrawingInfo(approved_by="K. Tanaka", date_of_issue="2026-02-30")


@pytest.mark.parametrize("prefix", ["../x", "a b", "", "-lead"])
def test_identification_prefix_rejects_unsafe_values(prefix: str):
    with pytest.raises(ValidationError):
        DrawingInfo(identification_prefix=prefix)


def test_title_rows_end_in_the_identification_zone():
    rows = _title_rows("demo", "shell", "ABS", "fdm", None, "ab" * 32)
    assert rows[0].startswith("TITLE") and "demo shell" in rows[0]
    assert rows[-3].startswith("OWNER")
    assert rows[-2].split() == ["ID", "NO.", "demo-shell", "REV", "A"]
    assert rows[-1].startswith("DATE") and rows[-1].endswith("SHEET 1/1")
    assert any(r.split() == ["STATUS", "In", "preparation"] for r in rows)
    assert any(r.endswith("abababababababab") for r in rows if r.startswith("BRIEF SHA"))


def test_title_rows_carry_contract_metadata():
    info = DrawingInfo(
        legal_owner="ACME K.K.",
        identification_prefix="ACME-001",
        revision="B",
        created_by="Y. Y",
        approved_by="K. T",
        date_of_issue="2026-10-05",
        classification="Internal",
        language="ja",
    )
    text = "\n".join(_title_rows("demo", "lid", None, None, info, None))
    for needle in (
        "ACME K.K.",
        "ACME-001-lid   REV B",
        "Released",
        "CLASS       Internal",
        "2026-10-05   LANG ja",
    ):
        assert needle in text
    assert "BRIEF SHA" not in text and "MATERIAL" not in text
