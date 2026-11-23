# Clone and setup

This procedure checks out the released verification snapshot, not the moving `develop` branch.

## Clone the repository

Run from the directory where you want the repository folder created:

~~~bash
git clone --no-checkout https://github.com/amosproj/amos2026ws01-legacy-migrator.git
cd amos2026ws01-legacy-migrator
git checkout sprint-05-release
~~~

The verification checkout resolved to `4ca343e28c87824856b5f5fb9d6a91cdc976d044`.

## Set up the backend

Use Python 3.12 and uv. From the repository root:

~~~bash
cd backend
uv sync --locked
~~~

This installs the query API, ingestion pipeline, and development tools into the shared backend environment. The API and pipeline use the same lockfile.

## Set up the frontend

Use Node 20 or Node 22. From the repository root:

~~~bash
cd frontend
npm ci
~~~

No `.env` file is needed for the default mock provider. See [Environment variables](Environment-variables) before configuring a real provider.
