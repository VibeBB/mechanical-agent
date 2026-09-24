ARG UV_VERSION=0.12.18
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM ubuntu:26.04

ARG DEBIAN_FRONTEND=noninteractive
ARG UV_VERSION=0.12.18
ARG IMAGE_REVISION=unknown

ENV DEBIAN_FRONTEND=noninteractive
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python
ENV PATH="/opt/mech/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
# Keep runtime bytecode caches out of the root-owned /opt/mech tree so the
# non-root `mech` user does not need write access to the sources.
ENV PYTHONPYCACHEPREFIX=/tmp/mech-pycache

LABEL org.opencontainers.image.source="https://github.com/VibeBB/mechanical-agent" \
      org.opencontainers.image.licenses="BSD-3-Clause" \
      org.opencontainers.image.revision="${IMAGE_REVISION}" \
      mech.uv.version="${UV_VERSION}"

COPY --from=uv /uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ca-certificates \
        curl \
        git \
        xz-utils \
        libgl1 \
        libglu1-mesa \
        libx11-6 \
        libxi6 \
        libxmu6 \
        libxrender1 \
        libxt6 \
        libxext6 \
        libfreetype6 \
        libfontconfig1 \
        librsvg2-bin \
    && rm -rf /var/lib/apt/lists/*

RUN uv python install 3.12 \
    && uv venv --python 3.12 /opt/mech/.venv

COPY pyproject.toml uv.lock /opt/mech/
COPY src /opt/mech/src
COPY plugins/mech /opt/mech/plugins/mech
COPY scripts/e2e_authoring.py /opt/mech/scripts/e2e_authoring.py
COPY examples /opt/mech/examples

RUN cd /opt/mech \
    && uv export --frozen --no-dev --no-emit-project --format requirements-txt \
        --output-file /tmp/mech-requirements.txt \
    && uv pip install --python /opt/mech/.venv/bin/python \
        --requirement /tmp/mech-requirements.txt \
    && uv pip install --python /opt/mech/.venv/bin/python --no-deps /opt/mech \
    && python -c "import build123d, mech, pydantic; print(mech.__version__)" \
    && python -m mech doctor \
    && rsvg-convert --version \
    && rm -f /tmp/mech-requirements.txt

RUN if ! getent group mech >/dev/null; then groupadd mech; fi \
    && if getent passwd 1000 >/dev/null; then \
         existing="$(getent passwd 1000 | cut -d: -f1)"; \
         if [ "$existing" != mech ]; then usermod --login mech --gid mech "$existing"; fi; \
         usermod --home /home/mech mech; \
       else \
         useradd --uid 1000 --gid mech --create-home --shell /bin/bash mech; \
       fi \
    && mkdir -p /home/mech/.cache \
    && chown -R mech:mech /home/mech

WORKDIR /opt/mech
