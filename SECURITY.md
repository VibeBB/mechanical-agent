# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Reporting a vulnerability

Please do not open public issues for security vulnerabilities. Report them
via GitHub's private vulnerability reporting on this repository, or by
contacting the maintainer directly. Include:

- the affected version/commit,
- a minimal reproduction (brief JSON, command, or payload),
- impact assessment if known.

You can expect an acknowledgement within a few days. We will coordinate a
fix and disclosure with you before publishing details.

## Scope notes

mech executes CAD generation and gate evaluation locally. The
`protect-generated` hook and fail-closed gates defend projection integrity
but are not a sandbox: do not run untrusted briefs in environments where a
crafted STEP/mesh file could reach other tooling — build123d/OCP parses
external CAD data as native code. The MCP server speaks stdio only and
never opens network listeners.
