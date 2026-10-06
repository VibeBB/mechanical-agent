"""Ruggedness brief and request for simulation-agent built from an enclosure brief."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .brief import DesignBrief, EnclosureSpec


def opening_min_dims(enclosure: EnclosureSpec) -> list[float]:
    """Smallest cross-dimension of every opening and vent slot (IP probe size)."""
    dims = [
        min(opening.width_mm, opening.height_mm) if opening.kind == "rect" else opening.width_mm
        for opening in enclosure.openings
    ]
    if enclosure.vent is not None:
        dims.append(enclosure.vent.slot_width_mm)
    return dims


def ruggedness_brief(brief: DesignBrief) -> dict[str, Any]:
    """``*.sim.json`` payload with a ``ruggedness`` section for simulation-agent."""
    enclosure = brief.enclosure
    if enclosure is None or enclosure.ruggedness is None:
        raise ValueError("enclosure.ruggedness is required for a ruggedness request")
    spec = enclosure.ruggedness
    section: dict[str, Any] = {}
    if spec.vibration is not None:
        if enclosure.board is None:
            raise ValueError("ruggedness vibration needs enclosure.board")
        if spec.board_material is None:
            raise ValueError("ruggedness vibration needs board_material")
        section["plate"] = {
            "width_mm": enclosure.board.width_mm,
            "depth_mm": enclosure.board.depth_mm,
            "thickness_mm": enclosure.board.thickness_mm,
            **spec.board_material.model_dump(),
        }
        section["vibration"] = spec.vibration.model_dump(exclude_none=True)
    if spec.drop is not None:
        section["drop"] = spec.drop.model_dump()
    if spec.ip_code is not None:
        section["ingress"] = {
            "code": spec.ip_code,
            "openings_min_mm": opening_min_dims(enclosure),
            "sealed": spec.sealed,
        }
    return {"schema_version": 1, "name": f"{brief.name}-ruggedness", "ruggedness": section}


def write_sim_request(
    brief: DesignBrief,
    out_dir: Path,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Write the sim brief and its v1 ``*.sim-request.json``; ``root`` relativises paths."""
    payload = ruggedness_brief(brief)
    out_dir.mkdir(parents=True, exist_ok=True)
    brief_path = out_dir / f"{brief.name}.ruggedness.sim.json"
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    brief_path.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    brief_ref = (brief_path.relative_to(root) if root is not None else brief_path).as_posix()
    checks = sorted(key for key in payload["ruggedness"] if key != "plate")
    request = {
        "schema_version": 1,
        "from_system": "mech",
        "request_id": f"{brief.name}-ruggedness-{digest[:12]}",
        "kind": "ruggedness",
        "brief_path": brief_ref,
        "question": (
            f"Run the {', '.join(checks)} ruggedness checks for the {brief.name} enclosure "
            "board and answer with a sim-response."
        ),
        "requested_by": "mech",
    }
    request_path = out_dir / f"{brief.name}.ruggedness.sim-request.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "verdict": "pass",
        "design": brief.name,
        "checks": checks,
        "sim_brief": brief_ref,
        "sim_brief_sha256": digest,
        "request": str(request_path),
        "request_id": request["request_id"],
    }
