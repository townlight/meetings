# syntax=docker/dockerfile:1.7

FROM --platform=linux/amd64 node:24-bookworm-slim@sha256:03eae3ef7e88a9de535496fb488d67e02b9d96a063a8967bae657744ecd513f2

ARG TOWNLIGHT_MEETINGS_REPO_URL=https://github.com/townlight/meetings.git
ARG TOWNLIGHT_MEETINGS_COMMIT
ARG TOWNLIGHT_CORE_REPO_URL=https://github.com/townlight/core.git
ARG TOWNLIGHT_CORE_COMMIT=3021821bf9a92c790a399ad12aed821d65b09105
ARG TOWNLIGHT_CORE_FREEZE_REF=v1.2.1
ARG COSIGN_VERSION=v3.0.6
ARG COSIGN_SHA256=c956e5dfcac53d52bcf058360d579472f0c1d2d9b69f55209e256fe7783f4c74

LABEL org.opencontainers.image.title="Townlight Meetings CC-1 cleanroom harness"
LABEL org.opencontainers.image.description="Pinned Townlight Core candidate with separate historical freeze provenance verification."

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN test -n "${TOWNLIGHT_MEETINGS_COMMIT}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        curl \
        git \
        gzip \
        gnupg \
        openssl \
        python3 \
        python3-venv \
        tar \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/townlight-meetings-venv \
    && /opt/townlight-meetings-venv/bin/python -m pip install --upgrade pip build
ENV PATH="/opt/townlight-meetings-venv/bin:${PATH}"

RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
        -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli

RUN docker --version

RUN curl -fsSL \
        "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-amd64" \
        -o /usr/local/bin/cosign \
    && echo "${COSIGN_SHA256}  /usr/local/bin/cosign" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/cosign \
    && cosign version

RUN git clone --filter=blob:none "${TOWNLIGHT_CORE_REPO_URL}" /workspace/townlight_core-freeze \
    && cd /workspace/townlight_core-freeze \
    && git fetch --depth 1 origin "${TOWNLIGHT_CORE_FREEZE_REF}" \
    && git checkout --detach "${TOWNLIGHT_CORE_FREEZE_REF}"

RUN git clone --filter=blob:none "${TOWNLIGHT_CORE_REPO_URL}" /workspace/townlight-core-candidate \
    && cd /workspace/townlight-core-candidate \
    && git fetch --depth 1 origin "${TOWNLIGHT_CORE_COMMIT}" \
    && git checkout --detach "${TOWNLIGHT_CORE_COMMIT}" \
    && test "$(git rev-parse HEAD)" = "${TOWNLIGHT_CORE_COMMIT}"

RUN git clone --filter=blob:none "${TOWNLIGHT_MEETINGS_REPO_URL}" /workspace/townlight_meetings \
    && cd /workspace/townlight_meetings \
    && git fetch --depth 1 origin "${TOWNLIGHT_MEETINGS_COMMIT}" \
    && git checkout --detach "${TOWNLIGHT_MEETINGS_COMMIT}" \
    && test "$(git rev-parse HEAD)" = "${TOWNLIGHT_MEETINGS_COMMIT}"

WORKDIR /workspace/townlight_meetings

RUN python scripts/install-core-candidate.py --core-source /workspace/townlight-core-candidate \
    && python -m pip install -e ".[dev]" \
    && npm --prefix frontend ci \
    && npx --prefix frontend playwright install --with-deps chromium

RUN install -m 0755 scripts/cleanroom/townlight_meetings-cleanroom-runner.sh /usr/local/bin/townlight_meetings-cleanroom-runner

ENV TOWNLIGHT_MEETINGS_REPO_URL="${TOWNLIGHT_MEETINGS_REPO_URL}"
ENV TOWNLIGHT_MEETINGS_COMMIT="${TOWNLIGHT_MEETINGS_COMMIT}"
ENV TOWNLIGHT_CORE_REPO_URL="${TOWNLIGHT_CORE_REPO_URL}"
ENV TOWNLIGHT_CORE_COMMIT="${TOWNLIGHT_CORE_COMMIT}"
ENV TOWNLIGHT_CORE_FREEZE_REF="${TOWNLIGHT_CORE_FREEZE_REF}"
ENV CLEANROOM_BASE_IMAGE="node:24-bookworm-slim"
ENV CLEANROOM_BASE_IMAGE_DIGEST="sha256:03eae3ef7e88a9de535496fb488d67e02b9d96a063a8967bae657744ecd513f2"
ENV CLEANROOM_COSIGN_VERSION="${COSIGN_VERSION}"
ENV CLEANROOM_COSIGN_SHA256="${COSIGN_SHA256}"

ENTRYPOINT ["townlight_meetings-cleanroom-runner"]
CMD ["online"]
