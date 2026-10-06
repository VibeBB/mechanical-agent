"""Expose the mech deterministic entry points over a stdio MCP transport.

Every tool returns a JSON text payload mirroring the CLI verdicts. The
transport never judges the design itself: observations carry no pass
authority beyond what the wrapped function returns. Import failures of the
CAD stack degrade to a fail-closed error result, not a crash.
"""

from __future__ import annotations

import asyncio
import base64
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
from .records import (
    DecisionInput,
    StageImpressionInput,
    VisionReviewInput,
    record_decision,
    record_impression,
    record_vision_review,
    records_summary,
)
from .standards import (
    BEARING_SEATS,
    ISO_METRIC_THREADS,
    MATERIALS,
    PROCESS_LIMITS,
)
from .workspace import reject_symlinks, workspace_path, workspace_root

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
            "render": {
                "type": "boolean",
                "default": True,
                "description": (
                    "also render every DXF and a views sheet per STEP (advisory "
                    "images for the vision lane); a render failure is reported "
                    "but never changes the gate verdict"
                ),
            },
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
    "mech_board_import": {
        "type": "object",
        "properties": {
            "geometry_path": {"type": "string"},
            "source_path": {"type": "string"},
        },
        "required": ["geometry_path"],
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
    "mech_render": {
        "type": "object",
        "properties": {
            "dxf_path": {"type": "string"},
            "out_path": {"type": "string"},
            "dpi": {"type": "integer", "exclusiveMinimum": 0},
            "baseline_path": {"type": "string"},
        },
        "required": ["dxf_path"],
        "additionalProperties": False,
    },
    "mech_render_section": {
        "type": "object",
        "properties": {
            "step": {"type": "string"},
            "axis": {"type": "string", "enum": ["x", "y", "z"]},
            "offset_mm": {"type": "number"},
            "baseline_path": {"type": "string"},
        },
        "required": ["step", "axis"],
        "additionalProperties": False,
    },
    "mech_render_views": {
        "type": "object",
        "properties": {
            "step": {"type": "string"},
            "envelope": {"type": "string"},
            "baseline_path": {"type": "string"},
        },
        "required": ["step"],
        "additionalProperties": False,
    },
    "mech_record_decision": DecisionInput.model_json_schema(),
    "mech_record_impression": StageImpressionInput.model_json_schema(),
    "mech_record_vision_review": VisionReviewInput.model_json_schema(),
    "mech_records_status": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "mech_ux_inbox": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "mech_ux_respond": {
        "type": "object",
        "properties": {
            "request": {"type": "string"},
            "status": {
                "type": "string",
                "enum": [
                    "accepted",
                    "in_progress",
                    "done",
                    "rejected",
                    "deferred",
                    "needs_info",
                ],
            },
            "reason": {"type": "string"},
            "artifacts": {"type": "array", "items": {"type": "string"}},
            "gate_verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "gate": {"type": "string"},
                        "verdict": {"type": "string", "enum": ["pass", "fail", "unknown"]},
                    },
                    "required": ["gate", "verdict"],
                    "additionalProperties": False,
                },
            },
            "design_reports": {"type": "array", "items": {"type": "string"}},
            "decision_refs": {"type": "array", "items": {"type": "string"}},
            "impression_refs": {"type": "array", "items": {"type": "string"}},
            "questions_for_user": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["request", "status"],
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
    "mech_board_import": (
        "Derive the enclosure board block (size, keepout, mount holes, hash pin) and "
        "connector opening targets from a circuit *.board-geometry.json."
    ),
    "mech_dxf_lint": "Advisory readability lint for a DXF drawing (never a gate verdict).",
    "mech_render": (
        "Rasterize an exported DXF to PNG for the advisory vision lane; "
        "optional sha256 visual baseline compare."
    ),
    "mech_render_section": (
        "Cut a STEP file with a plane normal to x, y or z (through the bbox centre "
        "plus offset_mm), draw the hatched section view and return the PNG inline "
        "with the cut area; fails when the plane misses the part."
    ),
    "mech_render_views": (
        "Project a STEP file into a 2x2 views sheet (front/top/right/isometric, "
        "hidden lines dashed) and return the PNG inline for visual review; "
        "optional envelope-anchor overlay and sha256 baseline."
    ),
    "mech_record_decision": (
        "Record a design decision (VibeBB Record Protocol): first principles, at least two "
        "options with pros/cons, the chosen option, a rationale of 200+ chars, evidence "
        "paths (hashed) or references, assumptions, unknowns, risks, revisit trigger. "
        "Record one for every non-trivial choice without being asked."
    ),
    "mech_record_impression": (
        "Record the long-form impression that closes a stage (400+ chars, 3+ sentences): "
        "what you noticed, what works, what worries you, how a maker or user would read "
        "it, what to do next. Binds the stage artifacts by sha256; record it after the "
        "final regeneration."
    ),
    "mech_record_vision_review": (
        "Record what you thought after looking at an image (400+ char impression plus "
        "findings). Bind it to image_path (hashed) or to the source_event_id of an "
        "inspect_image_with_vision event. Required for every image you viewed."
    ),
    "mech_records_status": (
        "Counts of decision / impression / vision-review records and the last Stop-hook "
        "verdict listing records this session still owes."
    ),
    "mech_ux_inbox": (
        "List UX-creator liaison requests targeting mech (SLP v2): per-request state "
        "new|answered|stale|blocked plus malformed request/response files."
    ),
    "mech_ux_respond": (
        "Write liaison/<id>.ux-response.json answering a UX-creator request (SLP v2). "
        "'done' needs all-pass gate verdicts, artifacts, and decision/impression refs "
        "into the VRP logs; use needs_info or rejected with a reason otherwise."
    ),
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


_IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def _image_content(path: Path) -> types.ImageContent | None:
    mime = _IMAGE_MIME.get(path.suffix.lower())
    if mime is None or not path.is_file():
        return None
    try:
        data = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return None
    return types.ImageContent(type="image", data=data, mimeType=mime)


def _path_arg(arguments: dict[str, Any], key: str) -> Path:
    return workspace_path(arguments[key])


def _optional_path_arg(arguments: dict[str, Any], key: str) -> Path | None:
    value = arguments.get(key)
    return workspace_path(value) if value else None


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
    out_dir = _path_arg(arguments, "out_dir")
    reject_symlinks(out_dir)
    design = generate(brief)
    if name == "mech_author":
        export_design(brief, design, out_dir)
    from .board_geometry import resolve_source

    report = run_gates(
        brief,
        design,
        out_dir,
        board_geometry_path=resolve_source(brief, workspace_root(), confine=True),
    )
    renders: list[dict[str, Any]] | dict[str, Any] | None = None
    if name == "mech_author" and bool(arguments.get("render", True)):
        from .render import RenderError
        from .views import render_author_outputs

        try:
            renders = render_author_outputs(brief.name, [p.part_id for p in design.parts], out_dir)
        except (RenderError, ValueError, OSError) as exc:
            renders = {"status": "error", "detail": str(exc)}
    report_path = write_report(brief, design, report, out_dir, renders=renders)
    payload = report.to_dict(brief)
    payload["report_path"] = str(report_path)
    assembly_views: str | None = None
    if isinstance(renders, list):
        payload["renders"] = renders
        for entry in renders:
            if entry["kind"] == "views" and entry["source"].endswith(f"/{brief.name}.step"):
                assembly_views = str(entry["png_path"])
                break
    elif renders is not None:
        payload["renders"] = renders
    result = _ok(payload)
    if assembly_views is not None:
        image = _image_content(Path(assembly_views))
        if image is not None:
            result.content.append(image)
    return result


def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
    try:
        if name == "mech_doctor":
            return _ok(run_doctor())
        if name == "mech_record_decision":
            return _ok(record_decision(arguments))
        if name == "mech_record_impression":
            return _ok(record_impression(arguments))
        if name == "mech_record_vision_review":
            return _ok(record_vision_review(arguments))
        if name == "mech_records_status":
            return _ok(records_summary())
        if name == "mech_ux_inbox":
            from .liaison import ux_inbox

            return _ok(ux_inbox())
        if name == "mech_ux_respond":
            from .liaison import ux_respond

            return _ok(ux_respond(dict(arguments)))
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
        if name == "mech_board_import":
            from .board_geometry import load_geometry, sha256_file, suggest_board

            geometry_path = _path_arg(arguments, "geometry_path")
            source = arguments.get("source_path") or str(arguments["geometry_path"])
            suggestion = suggest_board(
                load_geometry(geometry_path), str(source), sha256_file(geometry_path)
            )
            return _ok({"verdict": "pass", **suggestion})
        if name == "mech_export_envelope":
            from .brief import DesignBrief
            from .envelope import write_envelope

            brief = DesignBrief.model_validate(arguments["brief"])
            out_path_arg = _path_arg(arguments, "out_path")
            reject_symlinks(out_path_arg)
            out_path = write_envelope(brief, out_path_arg)
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

            drawing_path = _path_arg(arguments, "drawing_path")
            output_path = _optional_path_arg(arguments, "output_path")
            if output_path is not None:
                reject_symlinks(output_path)
            report = lint_file(
                drawing_path,
                output_path,
            )
            return _ok(report.model_dump(mode="json"))
        if name == "mech_render":
            from .render import render_dxf

            dxf_path = _path_arg(arguments, "dxf_path")
            out_path = _optional_path_arg(arguments, "out_path")
            baseline_path = _optional_path_arg(arguments, "baseline_path")
            for path in (out_path, baseline_path):
                if path is not None:
                    reject_symlinks(path)
            render = render_dxf(
                dxf_path,
                out_path,
                dpi=int(arguments.get("dpi", 200)),
                baseline_path=baseline_path,
            )
            payload: dict[str, Any] = {
                "verdict": "pass",
                "dxf_path": render.dxf_path,
                "svg_path": render.svg_path,
                "png_path": render.png_path,
                "image_sha256": render.image_sha256,
            }
            if render.baseline is not None:
                payload["baseline"] = render.baseline
                payload["baseline_sha256"] = render.baseline_sha256
            content: list[types.ContentBlock] = [
                types.TextContent(
                    type="text",
                    text=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                )
            ]
            image = _image_content(Path(render.png_path))
            if image is not None:
                content.append(image)
            return types.CallToolResult(content=content)
        if name == "mech_render_section":
            from .cli import section_payload
            from .views import render_section

            step_path = _path_arg(arguments, "step")
            baseline_path = _optional_path_arg(arguments, "baseline_path")
            if baseline_path is not None:
                reject_symlinks(baseline_path)
            offset = arguments.get("offset_mm", 0.0)
            if isinstance(offset, bool) or not isinstance(offset, int | float):
                return _error("offset_mm must be a number")
            section = render_section(
                step_path,
                axis=str(arguments.get("axis", "")),
                offset_mm=float(offset),
                baseline_path=baseline_path,
            )
            content = [
                types.TextContent(
                    type="text",
                    text=json.dumps(section_payload(section), ensure_ascii=False, sort_keys=True),
                )
            ]
            image = _image_content(Path(section.png_path))
            if image is not None:
                content.append(image)
            return types.CallToolResult(content=content)
        if name == "mech_render_views":
            from .views import render_views

            step_path = _path_arg(arguments, "step")
            envelope_path = _optional_path_arg(arguments, "envelope")
            baseline_path = _optional_path_arg(arguments, "baseline_path")
            for extra in (envelope_path, baseline_path):
                if extra is not None:
                    reject_symlinks(extra)
            views = render_views(
                step_path, envelope_path=envelope_path, baseline_path=baseline_path
            )
            payload = {
                "verdict": "pass",
                "step_path": views.step_path,
                "svg_path": views.svg_path,
                "png_path": views.png_path,
                "image_sha256": views.image_sha256,
                "views": list(views.views),
            }
            if views.baseline is not None:
                payload["baseline"] = views.baseline
                payload["baseline_sha256"] = views.baseline_sha256
            content = [
                types.TextContent(
                    type="text",
                    text=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                )
            ]
            image = _image_content(Path(views.png_path))
            if image is not None:
                content.append(image)
            return types.CallToolResult(content=content)
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
    "mech_board_import": _anno("Board geometry import", write=False),
    "mech_dxf_lint": _anno("DXF lint", write=False),
    "mech_render": _anno("Render DXF to PNG", write=True),
    "mech_render_views": _anno("Render STEP views sheet", write=True),
    "mech_render_section": _anno("Render STEP section view", write=True),
    "mech_record_decision": _anno("Record decision", write=True),
    "mech_record_impression": _anno("Record stage impression", write=True),
    "mech_record_vision_review": _anno("Record vision review", write=True),
    "mech_records_status": _anno("Records status", write=False),
    "mech_ux_inbox": _anno("Liaison inbox", write=False),
    "mech_ux_respond": _anno("Answer liaison request", write=True),
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
