"""Board envelope export for circuit-agent (``*.mech-board-envelope.json``).

Projects the enclosure's board cavity into the circuit board frame (origin at
the board centre, +y toward the back face): the board outline and mount holes
the standoffs expect, the part height allowed above and below the board, and
every side-face opening as an along-face span plus a z span measured from the
board top surface. circuit-agent pins the file by sha256 and gates its
placement against it (``circuit.enclosure``).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .brief import SIDE_FACES, DesignBrief, brief_sha256


def board_envelope_payload(brief: DesignBrief) -> dict[str, Any]:
    """Return the ``mech_board_envelope`` v1 payload for the brief."""
    spec = brief.enclosure
    if spec is None or spec.board is None:
        raise ValueError("brief declares no enclosure board")
    board = spec.board
    board_bottom = spec.floor_mm + spec.standoff_height_mm
    board_top = board_bottom + board.thickness_mm
    openings: list[dict[str, Any]] = []
    for opening in sorted(spec.openings, key=lambda item: (len(item.id), item.id)):
        if opening.face not in SIDE_FACES:
            continue
        span_z = opening.height_mm if opening.kind == "rect" else opening.width_mm
        centre_z = spec.height_mm / 2 + opening.center_y_mm - board_top
        openings.append(
            {
                "id": opening.id,
                "face": opening.face,
                "along_mm": [
                    round(opening.center_x_mm - opening.width_mm / 2, 4),
                    round(opening.center_x_mm + opening.width_mm / 2, 4),
                ],
                "z_mm": [round(centre_z - span_z / 2, 4), round(centre_z + span_z / 2, 4)],
            }
        )
    return {
        "schema_version": 1,
        "system": "mech",
        "artifact_kind": "mech_board_envelope",
        "frame": "board_center_y_up_mm",
        "design": brief.name,
        "brief_sha256": brief_sha256(brief),
        "board": {
            "width_mm": board.width_mm,
            "depth_mm": board.depth_mm,
            "thickness_mm": board.thickness_mm,
            "mount_holes": [
                {
                    "id": hole.id,
                    "x_mm": hole.x_mm,
                    "y_mm": hole.y_mm,
                    "diameter_mm": hole.diameter_mm,
                }
                for hole in board.mount_holes
            ],
        },
        "max_height_top_mm": round(spec.height_mm - spec.wall_mm - board_top, 4),
        "max_height_bottom_mm": round(spec.standoff_height_mm, 4),
        "openings": openings,
    }


def write_board_envelope(brief: DesignBrief, out_dir: Path) -> dict[str, Any]:
    """Write ``<name>.mech-board-envelope.json`` and return its path and sha256."""
    payload = board_envelope_payload(brief)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{brief.name}.mech-board-envelope.json"
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return {
        "verdict": "pass",
        "design": brief.name,
        "path": str(path),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "openings": [opening["id"] for opening in payload["openings"]],
    }
