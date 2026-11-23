# Build

## Backend

The Python service is run from source; this tag does not define a separate backend bundle command. Synchronize the locked environment from `backend/`:

~~~bash
cd backend
uv sync --locked
~~~

The optional backend container image build is part of the Compose procedure on the [Deployment](Deployment) page.

## Frontend

Install the locked packages and produce the static production bundle from `frontend/`:

~~~bash
cd frontend
npm ci
npm run build
~~~

The build runs TypeScript compilation followed by Vite. The generated site is placed in `frontend/dist/`. A successful build may emit a chunk-size advisory for the bundled diagramming libraries; the command still exits successfully.
