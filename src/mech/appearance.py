"""Cosmetic acceptance criteria and limit samples for production-engineering.

``write_appearance`` projects the brief's ``appearance`` block into
``<name>.mech-appearance.json``; production-engineering imports it as
``mech-appearance`` and binds every limit sample to a visual inspection.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .brief import DesignBrief, brief_sha256


def appearance_payload(brief: DesignBrief) -> dict[str, Any]:
    """Return the ``mech_appearance`` v1 payload for the brief."""
    appearance = brief.appearance
    if appearance is None:
        raise ValueError("brief declares no appearance block")
    surfaces = [
        {
            "face": surface.face,
            "cosmetic_class": surface.cosmetic_class,
            "defects": [
                limit.model_dump(mode="json")
                for limit in sorted(surface.defects, key=lambda item: item.defect)
            ],
        }
        for surface in sorted(appearance.surfaces, key=lambda item: item.face)
    ]
    samples = [
        sample.model_dump(mode="json")
        for sample in sorted(appearance.samples, key=lambda item: (len(item.id), item.id))
    ]
    return {
        "schema_version": 1,
        "system": "mech",
        "artifact_kind": "mech_appearance",
        "design": brief.name,
        "brief_sha256": brief_sha256(brief),
        "material": brief.material,
        "process": brief.process,
        "viewing": appearance.viewing.model_dump(mode="json"),
        "surfaces": surfaces,
        "samples": samples,
    }


def write_appearance(brief: DesignBrief, out_dir: Path) -> dict[str, Any]:
    """Write ``<name>.mech-appearance.json`` and return its path and sha256."""
    payload = appearance_payload(brief)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{brief.name}.mech-appearance.json"
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return {
        "verdict": "pass",
        "design": brief.name,
        "path": str(path),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "surfaces": [surface["face"] for surface in payload["surfaces"]],
        "samples": [sample["id"] for sample in payload["samples"]],
    }
