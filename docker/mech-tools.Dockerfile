ARG UV_VERSION=0.12.23
ARG UV_DIGEST=sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21
FROM ghcr.io/astral-sh/uv:${UV_VERSION}@${UV_DIGEST} AS uv

FROM debian:13-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a

ARG DEBIAN_FRONTEND=noninteractive
ARG UV_VERSION=0.12.23
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

RUN apt-get -o Acquire::Retries=5 update \
    && apt-get -o Acquire::Retries=5 install --no-install-recommends -y \
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
    # The pinned base digest keeps shipping libpcre2-8-0 10.46-1~deb13u2;
    # upgrade it in-build to the fixed deb13u3 (CVE-2026-103111) so the
    # publish-time Trivy gate stays green between base-digest bumps.
    && apt-get -o Acquire::Retries=5 install --no-install-recommends \
        --only-upgrade -y libpcre2-8-0 \
    && rm -rf /var/lib/apt/lists/*

# The uv-managed CPython bundles pip with vendored copies of urllib3,
# msgpack, and setuptools that nothing in the image invokes — dependencies
# install via uv and the shipped venv is pip-less — so strip the payload
# instead of shipping unused vulnerable vendored packages.
RUN uv python install 3.14 \
    && rm -rf /opt/uv-python/bin/pip* \
              /opt/uv-python/cpython-*/bin/pip* \
              /opt/uv-python/cpython-*/lib/python3.14/site-packages/pip \
              /opt/uv-python/cpython-*/lib/python3.14/site-packages/pip-*.dist-info \
              /opt/uv-python/cpython-*/lib/python3.14/ensurepip \
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
