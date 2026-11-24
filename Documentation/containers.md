# Build and publish the SunsetTracker images

To run the mid-project demo using published images, follow the
[tester setup](../SETUP.md).

## Build from source

From the repository root, run `docker compose up --build` for a development smoke
test with the mock LLM provider. Open <http://localhost:3000> and check
<http://localhost:8000/api/health>. Stop this stack with `docker compose down`.

To build an image pair for the tester launcher, use the integrated checkout
containing the graph pipeline and tester setup.

```bash
docker build --platform linux/amd64 -t sunsettracker-backend:local backend
docker build --platform linux/amd64 -t sunsettracker-frontend:local frontend
```

Select those two images with `SUNSETTRACKER_BACKEND_IMAGE` and
`SUNSETTRACKER_FRONTEND_IMAGE` as described in the [tester setup](../SETUP.md).

## Published images

| Image | Build context |
| --- | --- |
| `ghcr.io/amosproj/amos2026ws01-legacy-migrator-backend` | [backend/](../backend/) |
| `ghcr.io/amosproj/amos2026ws01-legacy-migrator-frontend` | [frontend/](../frontend/) |

The [container workflow](../.github/workflows/container-images.yml) builds both
images on `linux/amd64`. It publishes matching `sha-…` tags and rolling branch
tags such as `develop`. A version tag such as `v1.2.3` publishes image tag
`1.2.3`. Use a matching pair from the same build to reproduce a demo.

## Frontend and backend addresses

The React app calls the FastAPI backend directly at the origin baked in during
the frontend build. The default build uses `http://localhost:8000`. For a
different deployment, pass `--build-arg VITE_BACKEND_URL=https://your-api-host`
to `docker build` for the frontend and configure `CORS_ORIGINS` on the backend
to allow that deployment's frontend origin.
