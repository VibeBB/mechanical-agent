# mech Docker images

## Purpose

`mech-tools.Dockerfile` bundles the deterministic `mech` core (build123d/OCCT
kernel, gates, exporters) into a single execution environment published to
GHCR as `ghcr.io/vibebb/mech-tools`. The `mech-server` image is built on top
of it with the OpenHands agent-server (`openhands-sdk` agent_server docker
build, `--target source`).

Docker does not guarantee determinism. Time, locale, filesystem, and CPU
differences remain, so manifest hashes, timestamp normalization, independent
reload, and the gate rules stay required — the image pins the toolchain, not
the outputs.

## Contents

| Content | Pin |
| --- | --- |
| Debian | `13` slim (`debian:13-slim`) |
| uv | `0.12.18` (`ghcr.io/astral-sh/uv:0.12.18`, also `ARG UV_VERSION`) |
| Python | `3.12` via `uv python install` (matches `requires-python` and the CI matrix floor) |
| mech + runtime deps | `uv export --frozen --no-dev` from `uv.lock` |

The package is installed into `/opt/mech/.venv` (first on `PATH`). Source
tree, plugin, `e2e_authoring.py`, and `examples/` are copied to `/opt/mech`.
Runtime user is `mech` (uid 1000).

## Build

```bash
docker build \
  --file docker/mech-tools.Dockerfile \
  --build-arg IMAGE_REVISION="$(git rev-parse HEAD)" \
  --tag mech-tools:local \
  .
```

## Run

```bash
# environment probe
docker run --rm mech-tools:local python -m mech doctor

# deterministic authoring (writes artifacts into ./out)
docker run --rm --user mech -v "$PWD/out:/out" mech-tools:local \
  python /opt/mech/scripts/e2e_authoring.py \
    --brief /opt/mech/examples/enclosure.brief.json --out /out/enclosure
```

The published images are recorded in `docker/image-digests.json` by
`publish-mech-images.yml`; `locked-image-check.yml` pulls the digest-locked
image and re-runs the smoke check inside it.
