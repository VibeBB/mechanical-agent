# Documentation index

## Guides

- [architecture.md](architecture.md) — system structure, data flow, gate model, module reference — see also [reference.md](reference.md) for the per-module API index
- [workflow.md](workflow.md) — the conversational design workflow: stages, handoffs, records left
- [agents.md](agents.md) — the three task sub-agents and their contracts
- [skills.md](skills.md) — every SKILL.md and when it triggers
- [commands.md](commands.md) — `/mech:*` commands and the `python -m mech` CLI
- [mcp.md](mcp.md) — every `mech_*` MCP tool: inputs, outputs, errors, read/write
- [hooks.md](hooks.md) — every hook script, its event, and its behavior
- [contracts.md](contracts.md) — every JSON schema this repo produces or consumes
- [records-and-vision.md](records-and-vision.md) — VibeBB Record Protocol (VRP) and the vision lane for mech
- [sister-cooperation.md](sister-cooperation.md) — Sister Liaison Protocol (SLP v2) and sister interchange
- [performance-and-limits.md](performance-and-limits.md) — measured timings and hard limits from the code
- [operations.md](operations.md) — runbook: verification, releases, dependency updates
- [dependency-updates.md](dependency-updates.md) — adopted dependency versions and update decisions
- [development.md](development.md) — hacking on this repo: layout, test conventions, guard tests
- [Test coverage and test design](test-coverage.md) — C0/C1/C2/MCC/MC/DC and boundary coverage, floors, test-design techniques
- [improvement-notes.md](improvement-notes.md) — known gaps and follow-ups found during the refactor

## Research

- [research/cad-kernels.md](research/cad-kernels.md) — CAD kernel survey and selection basis
- [research/mechanical-domains.md](research/mechanical-domains.md) — mechanical design domain survey
- [research/sdk-v1.49.5-feature-evaluation.md](research/sdk-v1.49.5-feature-evaluation.md) — OpenHands SDK and uv update decisions
- [research/sdk-v1.49.6-feature-evaluation.md](research/sdk-v1.49.6-feature-evaluation.md) — OpenHands SDK and uv update decisions
- [research/sdk-v1.50.0-feature-evaluation.md](research/sdk-v1.50.0-feature-evaluation.md) — OpenHands SDK and uv update decisions
- [research/sdk-v1.50.1-feature-evaluation.md](research/sdk-v1.50.1-feature-evaluation.md) — OpenHands SDK/tools adoption decisions
- [research/sdk-v1.51.0-feature-evaluation.md](research/sdk-v1.51.0-feature-evaluation.md) — OpenHands SDK/tools/uv adoption decisions
- [research/sdk-v1.52.0-feature-evaluation.md](research/sdk-v1.52.0-feature-evaluation.md) — OpenHands SDK/tools adoption decisions
- [research/sdk-v1.53.0-feature-evaluation.md](research/sdk-v1.53.0-feature-evaluation.md) — OpenHands SDK/tools adoption decisions
- [research/ac-v1.25-feature-evaluation.md](research/ac-v1.25-feature-evaluation.md) — Agent Canvas v1.25 surface adopt/defer decisions

## Accepted ADRs

- [adr/ADR-0001-cad-kernel.md](adr/ADR-0001-cad-kernel.md) — build123d as the kernel; copyleft tools stay subprocess-only
- [adr/ADR-0002-gate-model.md](adr/ADR-0002-gate-model.md) — fail-closed deterministic gates; LLM/vision stay L2
- [adr/ADR-0003-vision-l2.md](adr/ADR-0003-vision-l2.md) — vision as an L2 aid for intake and review only
- [adr/ADR-0004-intake-attachment-materialization-and-evidence-binding.md](adr/ADR-0004-intake-attachment-materialization-and-evidence-binding.md) — intake attachment materialization and evidence binding
- [adr/ADR-0005-vision-render-and-review-records.md](adr/ADR-0005-vision-render-and-review-records.md) — DXF→PNG render, visual baseline, typed visual-review records
- [adr/ADR-0006-attest-published-tools-images.md](adr/ADR-0006-attest-published-tools-images.md) — attest published tools images and verify provenance for locked tools
- [adr/ADR-0007-vibebb-records-vision-liaison.md](adr/ADR-0007-vibebb-records-vision-liaison.md) — VRP v1 port, STEP views vision point, SLP v2 liaison, envelope provenance sidecar
- [adr/ADR-0008-iso7200-title-block.md](adr/ADR-0008-iso7200-title-block.md) — ISO 7200 DXF title block sourced from `brief.drawing`, derived document status, brief digest
- [adr/ADR-0009-structural-coverage.md](adr/ADR-0009-structural-coverage.md) — structural coverage gate (C0, C1, C2, MC/DC, boundaries)
