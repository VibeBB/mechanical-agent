# Third-Party Notices

mech is licensed BSD-3-Clause (see LICENSE). This file lists the third-party
components the project depends on and how they are used.

## Runtime dependencies (import-linked)

| Package | License | Use |
| --- | --- | --- |
| [build123d](https://github.com/gumyr/build123d) 0.11.1 | Apache-2.0 | CAD kernel: parametric modeling, booleans, STEP/STL/3MF/DXF export |
| OpenCASCADE (OCP, via build123d) | LGPL-2.1 w/ exception | Geometry kernel accessed only through build123d's Python API; the OCCT exception clause permits use as a library |
| [pydantic](https://github.com/pydantic/pydantic) | MIT | Schema validation for brief/intake/report contracts |
| [mcp](https://github.com/modelcontextprotocol/python-sdk) | MIT | stdio MCP server boundary |
| [openhands-sdk](https://github.com/OpenHands/software-agent-sdk) 1.49.4 | MIT | Plugin framework (skills, agents, commands, hooks, task sub-agents) |
| openhands-tools 1.49.4 | MIT | SDK builtin tools used by sub-agents |
| [ezdxf](https://github.com/mozman/ezdxf) (via build123d) | MIT | DXF export backend |

## Container image components

The `mech-tools` image bundles the following third-party components:

| Component | License | Use |
| --- | --- | --- |
| uv (binary, copied from `ghcr.io/astral-sh/uv`) | Apache-2.0 OR MIT | Python environment and interpreter provisioning |
| Debian base image (`debian:13-slim`) | various (per-package copyrights in `/usr/share/doc/`) | base image + system libraries for OCP (mesa, X11, freetype) |

## Development tools

| Tool | License |
| --- | --- |
| ruff | MIT |
| pyright | MIT |
| pytest / pytest-xdist | MIT |
| uv | Apache-2.0/MIT |
| zizmor | MIT |

## Explicitly not linked

The following are **not** import-linked because of copyleft licensing; any
future integration must run them as unmodified subprocesses behind an
adapter (see docs/adr/ADR-0001-cad-kernel.md):

- FreeCAD — LGPL-2.0-or-later
- OpenSCAD — GPL-2.0-or-later
- CalculiX — GPL-2.0-or-later
- gmsh — GPL-2.0-or-later (with limited exception)

Licenses referenced above are available from each project's repository.
The OCCT exception text: https://dev.opencascade.org/resources/licensing
