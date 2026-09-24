"""Expose the mech deterministic entry points over a stdio MCP transport.

Every tool returns a JSON text payload mirroring the CLI verdicts. The
transport never judges the design itself: observations carry no pass
authority beyond what the wrapped function returns. Import failures of the
CAD stack degrade to a fail-closed error result, not a crash.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from . import __version__
from .doctor import run_doctor
from .standards import (
    BEARING_SEATS,
    ISO_METRIC_THREADS,
    MATERIALS,
    PROCESS_LIMITS,
)

server: Server = Server(f"mech-mcp/{__version__}")

_SCHEMAS: dict[str, dict[str, Any]] = {
    "mech_doctor": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "mech_standards": {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["materials", "processes", "threads", "bearings"],
            }
        },
        "required": ["kind"],
        "additionalProperties": False,
    },
    "mech_validate_brief": {
        "type": "object",
        "properties": {"brief": {"type": "object"}},
        "required": ["brief"],
        "additionalProperties": False,
    },
    "mech_intake": {
        "type": "object",
        "properties": {
            "brief": {"type": "object"},
            "intake": {"type": "object"},
        },
        "required": ["brief", "intake"],
        "additionalProperties": False,
    },
    "mech_fit_lookup": {
        "type": "object",
        "properties": {
            "nominal_mm": {"type": "number", "exclusiveMinimum": 0},
            "hole_class": {"type": "string"},
            "shaft_class": {"type": "string"},
            "intent": {
                "type": "string",
                "enum": ["clearance", "transition", "interference"],
            },
        },
        "required": ["nominal_mm", "hole_class", "shaft_class", "intent"],
        "additionalProperties": False,
    },
    "mech_author": {
        "type": "object",
        "properties": {
            "brief": {"type": "object"},
            "out_dir": {"type": "string"},
        },
        "required": ["brief", "out_dir"],
        "additionalProperties": False,
    },
    "mech_gates": {
        "type": "object",
        "properties": {
            "brief": {"type": "object"},
            "out_dir": {"type": "string"},
        },
        "required": ["brief", "out_dir"],
        "additionalProperties": False,
    },
    "mech_export_envelope": {
        "type": "object",
        "properties": {
            "brief": {"type": "object"},
            "out_path": {"type": "string"},
        },
        "required": ["brief", "out_path"],
        "additionalProperties": False,
    },
    "mech_dxf_lint": {
        "type": "object",
        "properties": {
            "drawing_path": {"type": "string"},
            "output_path": {"type": "string"},
        },
        "required": ["drawing_path"],
        "additionalProperties": False,
    },
}

_DESCRIPTIONS = {
    "mech_doctor": "Probe the CAD environment (build123d/OCP, exporters); JSON verdict.",
    "mech_standards": "List built-in materials, process limits, ISO threads, bearing seats.",
    "mech_validate_brief": "Validate a design brief JSON; returns parsed summary or issues.",
    "mech_intake": "Check an intake document against a brief (R*/A*/Q* coverage).",
    "mech_fit_lookup": "Evaluate one ISO limits-and-fits pair (clearance window + class).",
    "mech_author": "Generate parts, export artifacts, run all gates, write the design report.",
    "mech_gates": "Regenerate the design and re-run all gates against out_dir artifacts.",
    "mech_export_envelope": (
        "Emit the wire-agent EnvelopeSource contract (*.envelope.json) from brief harness_anchors."
    ),
    "mech_dxf_lint": "Advisory readability lint for a DXF drawing (never a gate verdict).",
}


def _ok(payload: dict[str, Any]) -> types.CallToolResult:
    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            )
        ]
    )


def _error(reason: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"ok": False, "fail_closed": True, "failure_reason": reason},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        ],
        isError=True,
    )


def _standards_payload(kind: str) -> dict[str, Any]:
    if kind == "materials":
        return {
            "verdict": "pass",
            "materials": {
                key: {
                    "name": m.name,
                    "allowable_strain": m.allowable_strain,
                    "living_hinge_max_mm": m.living_hinge_max_mm,
                    "min_bend_radius_factor": m.min_bend_radius_factor,
                }
                for key, m in MATERIALS.items()
            },
        }
    if kind == "processes":
        return {
            "verdict": "pass",
            "processes": {key: vars(p) for key, p in PROCESS_LIMITS.items()},
        }
    if kind == "threads":
        return {
            "verdict": "pass",
            "threads": {key: vars(t) for key, t in ISO_METRIC_THREADS.items()},
        }
    return {
        "verdict": "pass",
        "bearings": dict(BEARING_SEATS),
    }


def _run_pipeline(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
    """Heavy commands: brief-authoring path (may import the CAD kernel)."""
    from .brief import DesignBrief
    from .export import export_design
    from .gates import run_gates
    from .generators import generate
    from .report import write_report

    brief = DesignBrief.model_validate(arguments["brief"])
    out_dir = Path(arguments["out_dir"])
    design = generate(brief)
    if name == "mech_author":
        export_design(brief, design, out_dir)
    report = run_gates(brief, design, out_dir)
    report_path = write_report(brief, design, report, out_dir)
    payload = report.to_dict(brief)
    payload["report_path"] = str(report_path)
    return _ok(payload)


def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
    try:
        if name == "mech_doctor":
            return _ok(run_doctor())
        if name == "mech_standards":
            return _ok(_standards_payload(arguments["kind"]))
        if name == "mech_fit_lookup":
            from .fits import evaluate_fit

            result = evaluate_fit(
                arguments["nominal_mm"],
                arguments["hole_class"],
                arguments["shaft_class"],
                arguments["intent"],
            )
            return _ok({"verdict": "pass", "fit": dataclasses.asdict(result)})
        if name == "mech_validate_brief":
            from .brief import DesignBrief, brief_sha256

            brief = DesignBrief.model_validate(arguments["brief"])
            return _ok(
                {
                    "verdict": "pass",
                    "brief": {
                        "name": brief.name,
                        "design_type": brief.design_type,
                        "part_ids": brief.part_ids(),
                        "brief_sha256": brief_sha256(brief),
                    },
                }
            )
        if name == "mech_intake":
            from .brief import DesignBrief
            from .intake import Intake, check_intake

            brief = DesignBrief.model_validate(arguments["brief"])
            intake = Intake.model_validate(arguments["intake"])
            report = check_intake(brief, intake, Path("<inline>"), Path("<inline>"))
            return _ok(report.model_dump(mode="json"))
        if name == "mech_export_envelope":
            from .brief import DesignBrief
            from .envelope import write_envelope

            brief = DesignBrief.model_validate(arguments["brief"])
            out_path = write_envelope(brief, Path(arguments["out_path"]))
            return _ok(
                {
                    "verdict": "pass",
                    "design": brief.name,
                    "anchors": [anchor.name for anchor in brief.harness_anchors],
                    "out": str(out_path),
                }
            )
        if name in ("mech_author", "mech_gates"):
            return _run_pipeline(name, arguments)
        if name == "mech_dxf_lint":
            from .dxf_lint import lint_file

            report = lint_file(
                Path(arguments["drawing_path"]),
                Path(arguments["output_path"]) if arguments.get("output_path") else None,
            )
            return _ok(report.model_dump(mode="json"))
        return _error(f"unknown mech tool: {name}")
    except Exception as exc:  # fail-closed transport boundary
        return _error(str(exc))


def _anno(title: str, *, write: bool) -> types.ToolAnnotations:
    return types.ToolAnnotations(
        title=title,
        readOnlyHint=not write,
        destructiveHint=write,
        idempotentHint=True,
        openWorldHint=False,
    )


_ANNOTATIONS: dict[str, types.ToolAnnotations] = {
    "mech_doctor": _anno("Mech doctor", write=False),
    "mech_standards": _anno("Mech standards", write=False),
    "mech_validate_brief": _anno("Validate design brief", write=False),
    "mech_intake": _anno("Intake gate", write=False),
    "mech_fit_lookup": _anno("ISO fit lookup", write=False),
    "mech_author": _anno("Author design", write=True),
    "mech_gates": _anno("Re-run gates", write=True),
    "mech_export_envelope": _anno("Export envelope contract", write=True),
    "mech_dxf_lint": _anno("DXF lint", write=False),
}


def tool_specs() -> list[types.Tool]:
    return [
        types.Tool(
            name=name,
            description=_DESCRIPTIONS[name],
            inputSchema=_SCHEMAS[name],
            annotations=_ANNOTATIONS[name],
        )
        for name in _SCHEMAS
    ]


@server.list_tools()  # type: ignore[misc]
async def list_tools() -> list[types.Tool]:
    return tool_specs()


@server.call_tool()  # type: ignore[misc]
async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> types.CallToolResult:
    return await asyncio.to_thread(call_tool, name, arguments or {})


async def _serve() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="mech",
                server_version=__version__,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
