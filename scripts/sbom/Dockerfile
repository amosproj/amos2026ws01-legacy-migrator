FROM node:25-bookworm-slim@sha256:81db02c4b671288a03915da9534dbd54f96d0e7c24d80ccc54f5b36b2e684370
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash build-essential ca-certificates curl git python3 \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_VERSION=0.13.9 sh
RUN curl -sSfL https://raw.githubusercontent.com/anchore/syft/v1.57.2/install.sh \
    | sh -s -- -b /usr/local/bin v1.57.2
