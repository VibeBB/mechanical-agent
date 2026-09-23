"""Environment doctor: probe the tools the pipeline depends on.

Every check reports "pass" (capability present) or "fail" (missing/broken).
The verdict is fail-closed: any failed capability fails the report.
"""

from __future__ import annotations

import importlib
import platform
import sys
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class DoctorCheck:
    capability: str
    status: Literal["pass", "fail"]
    detail: str


def _probe_module(name: str, attr: str | None = None) -> DoctorCheck:
    try:
        module = importlib.import_module(name)
    except Exception as exc:
        return DoctorCheck(name, "fail", f"import failed: {exc}")
    version = getattr(module, "__version__", "unknown")
    if attr is not None and not hasattr(module, attr):
        return DoctorCheck(name, "fail", f"missing attribute {attr}")
    return DoctorCheck(name, "pass", f"version {version}")


def _probe_kernel() -> DoctorCheck:
    """Create a small boolean with the OCP kernel."""
    try:
        build123d = importlib.import_module("build123d")
        solid = build123d.Box(1, 1, 1) - build123d.Cylinder(0.2, 2)
        ok = bool(solid.is_valid) and solid.volume > 0
        return DoctorCheck(
            "ocp-kernel",
            "pass" if ok else "fail",
            "boolean probe produced a valid solid" if ok else "probe invalid",
        )
    except Exception as exc:
        return DoctorCheck("ocp-kernel", "fail", f"probe failed: {exc}")


def _probe_exporters() -> DoctorCheck:
    try:
        build123d = importlib.import_module("build123d")
        missing = [
            name
            for name in ("export_step", "export_stl", "Mesher", "ExportDXF")
            if not hasattr(build123d, name)
        ]
        if missing:
            return DoctorCheck("exporters", "fail", f"missing exporters: {', '.join(missing)}")
        return DoctorCheck("exporters", "pass", "step/stl/3mf/dxf exporters present")
    except Exception as exc:
        return DoctorCheck("exporters", "fail", str(exc))


def run_doctor() -> dict[str, Any]:
    py_ok = sys.version_info >= (3, 12)
    checks = [
        DoctorCheck(
            "python",
            "pass" if py_ok else "fail",
            f"{platform.python_version()} (>= 3.12 required)",
        ),
        _probe_module("pydantic"),
        _probe_module("build123d"),
        _probe_module("ezdxf"),
        _probe_kernel(),
        _probe_exporters(),
    ]
    return {
        "schema_version": 1,
        "checks": [
            {"capability": c.capability, "status": c.status, "detail": c.detail} for c in checks
        ],
        "verdict": "pass" if all(c.status == "pass" for c in checks) else "fail",
    }


__all__ = ["DoctorCheck", "run_doctor"]
