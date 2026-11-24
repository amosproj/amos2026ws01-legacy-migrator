# Clone and setup

## Clone the verified snapshot

Run from the directory where you want the repository folder created:

~~~bash
git clone https://github.com/amosproj/amos2026ws01-legacy-migrator.git
cd amos2026ws01-legacy-migrator
git checkout sprint-05-release
~~~

This is the `develop` snapshot used for this guide.

## Set up the backend

From the repository root:

~~~bash
cd backend
uv sync --locked
~~~

This installs the API, ingestion pipeline, and development tools into the shared backend environment.

## Set up the frontend

Use Node 20 or 22. From the repository root:

~~~bash
cd frontend
npm ci
~~~

The backend and frontend lockfiles keep installs reproducible.
