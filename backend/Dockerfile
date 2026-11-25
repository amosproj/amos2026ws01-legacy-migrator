# SunsetTracker backend image (ticket #82): FastAPI query API.
# Mirrors backend/run.sh: uv-managed Python 3.12 environment. By default the
# container starts with the built-in mock provider — no model endpoint needed.
# To use a real LLM, set LLM_BASE_URL and LLM_NAME via docker compose .env or
# `docker run -e`. host.docker.internal needs the host-gateway mapping on Linux
# (docker-compose.yml includes it; docker run needs --add-host).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Dependencies first so this layer is cached between source changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app/ app/
COPY shared_contracts/ shared_contracts/
COPY schemas/ schemas/

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER 10001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
