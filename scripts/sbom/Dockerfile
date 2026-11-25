FROM node:22-bookworm-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash build-essential ca-certificates curl git python3 \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_VERSION=0.13.9 sh
RUN curl -sSfL https://raw.githubusercontent.com/anchore/syft/v1.57.2/install.sh \
    | sh -s -- -b /usr/local/bin v1.57.2
