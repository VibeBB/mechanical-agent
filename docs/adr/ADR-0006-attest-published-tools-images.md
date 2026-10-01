# ADR-0006: Attest published tools images

Status: Accepted
Date: 2026-05-05

## Context

The `mech_tools` digest lock identifies the image used by the launcher, but a
digest alone does not establish which workflow built and published it.

## Decision

The image publish workflow creates a GitHub build-provenance attestation for
`ghcr.io/vibebb/mech-tools` and stores its URL in the root and plugin tools
locks. The locked-image workflow verifies available provenance with
`gh attestation verify`, restricted to the repository's publish workflow.
Older pins without attestation metadata warn and continue so existing locks
remain usable. The separate `mech_server` lock is not covered by this
tools-image attestation flow.

## Consequences

New tools-image pins carry a provenance reference that the smoke workflow can
verify. The workflow requires OIDC and attestation-write permissions to
publish the statement, and attestation-read permission to verify it.
