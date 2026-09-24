"""Deterministic readability lint for exported DXF drawings.

Advisory companion to the gates: it inspects a generated DXF for
readability and model-integrity issues — empty outlines, missing
frame/title/dimension furniture, text placed outside the frame, colliding
text, and undersized labels. It never promotes a verdict: errors mean the
emitted drawing is broken (fail-closed for the lint itself), warnings are
review aids.
"""

# ezdxf's annotations are only partially typed.
# pyright: reportPrivateImportUsage=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import argparse
import io
from pathlib import Path
from typing import Any, Literal

import ezdxf
from pydantic import BaseModel, ConfigDict, Field


class DxfLintError(ValueError):
    """Raised when a DXF file cannot be linted."""


class DxfLintFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    severity: Literal["error", "warning"]
    description: str
    items: list[str] = Field(default_factory=lambda: list[str]())


class DxfLintReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["dxf_lint"] = "dxf_lint"
    source: Path
    verdict: Literal["pass", "fail"]
    errors: int
    warnings: int
    entities_checked: int
    findings: list[DxfLintFinding] = Field(default_factory=lambda: list[DxfLintFinding]())


_MIN_LEGIBLE_TEXT_MM = 1.0
_TEXT_WIDTH_RATIO = 0.7  # char width estimate relative to text height
_TEXT_LINE_RATIO = 1.4  # line pitch estimate relative to text height
_OVERLAP_EPSILON = 0.05  # mm^2 — touching edges are fine, real overlaps are not


def _entities(msp: Any, layer: str, dxftype: str | None = None) -> list[Any]:
    return [e for e in msp if e.dxf.layer == layer and (dxftype is None or e.dxftype() == dxftype)]


def _frame_rect(msp: Any) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Bounding rect of the FRAME-layer border polyline, when present."""
    for entity in _entities(msp, "FRAME", "LWPOLYLINE"):
        points = list(entity.get_points("xy"))
        if not entity.closed or len(points) < 4:
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return (min(xs), min(ys)), (max(xs), max(ys))
    return None


def _text_box(entity: Any) -> tuple[float, float, float, float]:
    """Approximate (x, y, w, h) box for a TEXT entity at its insert point."""
    text = entity.dxf.text
    height = max(entity.dxf.height, 0.01)
    width = max(len(text), 1) * height * _TEXT_WIDTH_RATIO
    return (entity.dxf.insert.x, entity.dxf.insert.y, width, height * _TEXT_LINE_RATIO)


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    width = min(ax + aw, bx + bw) - max(ax, bx)
    height = min(ay + ah, by + bh) - max(ay, by)
    return width * height if width > 0 and height > 0 else 0.0


def _lint_doc(doc: Any, source: Path) -> DxfLintReport:
    msp = doc.modelspace()
    entities = list(msp)
    findings: list[DxfLintFinding] = []

    outline = _entities(msp, "0")
    if not outline:
        findings.append(
            DxfLintFinding(
                type="empty_outline",
                severity="error",
                description="no drawing entities on the outline layer (layer 0)",
            )
        )

    frame = _frame_rect(msp)
    if frame is None:
        findings.append(
            DxfLintFinding(
                type="missing_frame",
                severity="warning",
                description="no closed FRAME-layer border polyline; drawing lacks a frame",
            )
        )

    title_texts = _entities(msp, "TITLE", "TEXT")
    if not title_texts:
        findings.append(
            DxfLintFinding(
                type="missing_title",
                severity="warning",
                description="no TITLE-layer text; drawing lacks a title block",
            )
        )

    dim_texts = _entities(msp, "DIMS", "TEXT")
    if not dim_texts:
        findings.append(
            DxfLintFinding(
                type="missing_dimensions",
                severity="warning",
                description="no DIMS-layer text; drawing lacks dimension callouts",
            )
        )

    texts = [e for e in entities if e.dxftype() == "TEXT"]
    if frame is not None:
        (fx0, fy0), (fx1, fy1) = frame
        for entity in texts:
            x, y, w, h = _text_box(entity)
            if x < fx0 or y < fy0 or x + w > fx1 or y + h > fy1:
                findings.append(
                    DxfLintFinding(
                        type="text_out_of_frame",
                        severity="warning",
                        description=(
                            f"text {entity.dxf.text!r} at "
                            f"({x:.1f},{y:.1f}) extends past the drawing frame"
                        ),
                        items=[entity.dxf.text],
                    )
                )

    for entity in texts:
        height = entity.dxf.height
        if 0 < height < _MIN_LEGIBLE_TEXT_MM:
            findings.append(
                DxfLintFinding(
                    type="undersized_text",
                    severity="warning",
                    description=(
                        f"text {entity.dxf.text!r} height {height:.2f}mm is below "
                        f"{_MIN_LEGIBLE_TEXT_MM}mm and may be illegible"
                    ),
                    items=[entity.dxf.text],
                )
            )

    boxes = [(entity.dxf.text, _text_box(entity)) for entity in texts]
    for i, (label_a, box_a) in enumerate(boxes):
        for label_b, box_b in boxes[i + 1 :]:
            area = _overlap(box_a, box_b)
            if area > _OVERLAP_EPSILON:
                findings.append(
                    DxfLintFinding(
                        type="text_overlap",
                        severity="warning",
                        description=(
                            f"texts {label_a!r} and {label_b!r} overlap by "
                            f"{area:.1f} mm^2; labels may be unreadable"
                        ),
                        items=[label_a, label_b],
                    )
                )

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    return DxfLintReport(
        source=source,
        verdict="fail" if errors else "pass",
        errors=errors,
        warnings=warnings,
        entities_checked=len(entities),
        findings=findings,
    )


def lint_text(text: str, *, source: Path) -> DxfLintReport:
    try:
        doc = ezdxf.read(io.StringIO(text))
    except Exception as exc:
        raise DxfLintError(f"could not parse DXF: {exc}") from exc
    return _lint_doc(doc, source)


def lint_file(path: Path, output: Path | None = None) -> DxfLintReport:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        report = lint_text(text, source=path)
    except (OSError, DxfLintError) as exc:
        report = DxfLintReport(
            source=path,
            verdict="fail",
            errors=1,
            warnings=0,
            entities_checked=0,
            findings=[
                DxfLintFinding(
                    type="parse_error",
                    severity="error",
                    description=str(exc),
                )
            ],
        )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Advisory readability lint for a DXF drawing")
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = lint_file(args.drawing, args.output)
    print(report.model_dump_json(indent=2))
    return 0 if report.verdict == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
