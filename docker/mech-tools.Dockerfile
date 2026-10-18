ARG UV_VERSION=0.13.1
ARG UV_DIGEST=sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336
FROM ghcr.io/astral-sh/uv:${UV_VERSION}@${UV_DIGEST} AS uv

FROM debian:13-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f

ARG DEBIAN_FRONTEND=noninteractive
ARG UV_VERSION=0.13.1
ARG IMAGE_REVISION=unknown

# Fail the build when the left side of a verification/detection pipe
# (e.g. getent|cut) breaks instead of silently passing the right side.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

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

# apt resilience: Acquire::Retries covers single fetches, not a mirror that
# is down for minutes (archive.ubuntu.com outage killed several builds).
# Retry the whole update+install round with bounded backoff.
RUN for attempt in 1 2 3 4 5; do \
        apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update \
        && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install --no-install-recommends -y \
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
            libxt6t64 \
            libxext6 \
            libfreetype6 \
            libfontconfig1 \
            librsvg2-bin \
        # Apply every Debian security fix published after the pinned base
        # digest so the publish Trivy gate cannot trip on fixable findings
        # (apt always pulls the latest published fix).
        && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 upgrade -y --no-install-recommends \
        && rm -rf /var/lib/apt/lists/* \
        && break; \
        [ "$attempt" = 5 ] && exit 1; \
        echo "::warning::apt update+install attempt ${attempt} failed; retrying"; \
        sleep $((attempt * 30)); \
    done

# The uv-managed CPython bundles pip with vendored copies of urllib3,
# msgpack, and setuptools that nothing in the image invokes — dependencies
# install via uv and the shipped venv is pip-less — so strip the payload
# instead of shipping unused vulnerable vendored packages.
RUN uv python install 3.14 \
    && rm -rf /opt/uv-python/bin/pip* \
              /opt/uv-python/cpython-*/bin/pip* \
              /opt/uv-python/cpython-*/lib/python3.*/site-packages/pip \
              /opt/uv-python/cpython-*/lib/python3.*/site-packages/pip-*.dist-info \
              /opt/uv-python/cpython-*/lib/python3.*/ensurepip \
              /root/.cache/uv \
    && uv venv --python 3.14 /opt/mech/.venv

COPY pyproject.toml uv.lock /opt/mech/
COPY src /opt/mech/src
COPY plugins/mech /opt/mech/plugins/mech
COPY scripts/e2e_authoring.py /opt/mech/scripts/e2e_authoring.py
COPY examples /opt/mech/examples

WORKDIR /opt/mech

RUN uv export --frozen --no-dev --no-emit-project --format requirements-txt \
        --output-file /tmp/mech-requirements.txt \
    && uv pip install --python /opt/mech/.venv/bin/python \
        --requirement /tmp/mech-requirements.txt \
    && uv pip install --python /opt/mech/.venv/bin/python --no-deps /opt/mech \
    && python -c "import build123d, mech, pydantic; print(mech.__version__)" \
    && python -m mech doctor \
    && rsvg-convert --version \
    && rm -f /tmp/mech-requirements.txt

# Tighten the login.defs umask to 027 (Lynis AUTH-9328): the image has no
# interactive users, so files created at runtime stay group-readable only.
RUN printf 'UMASK 027\n' >> /etc/login.defs

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
