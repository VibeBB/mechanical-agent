## SBOM attestations

The publisher generates an SPDX-2.3 SBOM for the digest-pinned tools image,
attests it with predicate type `https://spdx.dev/Document/v2.3`, and uploads
the artifact for 30 days. The returned URL is stored as `sbom_attestation`;
locked-image checks verify it when present and warn when absent. Unpinned
locks cannot carry this metadata.
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

## Launcher-side verification

`MECH_VERIFY_ATTESTATION` accepts `auto` (the default), `require`, or `off`.
Before pulling a lock-provided image, and on every `prewarm`, the launcher
uses `gh attestation verify` with the lock entry and publisher workflow.
`auto` prints one note and skips for an image override, missing attestation,
missing `gh`, or failed `gh auth status`; once verification starts, failure
or timeout prevents the pull. `require` makes skip conditions errors, while
`off` never verifies. Ordinary invocations do not re-verify a locally
present image, and `--warn` doctor paths never verify.
