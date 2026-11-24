# SunsetTracker tester setup

Use the prebuilt images to run the mid-project demo. Docker runs the import,
Neo4j, the backend, and the frontend. The host runs Ollama. Python, `uv`,
Node.js, and npm are only needed for development from source.

## 1. Install the host tools

| Tool | Linux | macOS | Windows |
| --- | --- | --- | --- |
| Git | [Git download](https://git-scm.com/downloads) | [Git download](https://git-scm.com/downloads) | [Git for Windows](https://git-scm.com/download/win) |
| Docker with Compose | [Docker Engine](https://docs.docker.com/engine/install/) and the [Compose plugin](https://docs.docker.com/compose/install/linux/) or [Docker Desktop](https://docs.docker.com/desktop/setup/install/linux/) | [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/) | [Docker Desktop with the WSL 2 backend](https://docs.docker.com/desktop/setup/install/windows-install/) |
| Ollama | [Ollama download](https://ollama.com/download) | [Ollama download](https://ollama.com/download) | [Ollama download](https://ollama.com/download/windows) |
| Shell | Bash and `curl` | Bash and `curl` | PowerShell |

Run Docker in Linux-container mode on Docker Desktop. On Linux, the launcher
can start a systemd-managed Docker service and may prompt for `sudo`. Configure
your user for Docker during installation. The launcher starts local Ollama
when needed and downloads `qwen3.5:2b` on first use.
The published app images use `linux/amd64`. Docker Desktop uses emulation on
Apple Silicon. ARM Linux hosts need AMD64 emulation configured separately.
[Docker multi-platform builds](https://docs.docker.com/build/building/multi-platform/)

## 2. Prepare the reference checkout once

Use a GitHub account with access to the application, its images, and the
reference repositories. If GitHub Container Registry requires authentication,
sign in with `docker login ghcr.io`.

Clone the reference repository **next to** the SunsetTracker checkout. Run
this from the directory that contains the SunsetTracker checkout.

```sh
git clone --recurse-submodules https://github.com/legacy-modernization-example/legacy-example-stages.git
```

For a clone you already have, initialize its submodules if needed.

```sh
git -C legacy-example-stages submodule update --init --recursive
```

The launcher reads that checkout and imports the pinned `step-06` revisions.
Keep the reference checkout in a location Docker Desktop can mount. To use
another location, pass its path to the launcher.

## 3. Start from the SunsetTracker repo root

Linux and macOS

```bash
./run-tester.sh
# With another reference checkout:
./run-tester.sh "/path/to/legacy-example-stages"
```

Windows

```powershell
.\run-tester.ps1
# With another reference checkout:
.\run-tester.ps1 -ReferenceSource "C:\Projects\legacy-example-stages"
```

If PowerShell's policy blocks the cloned script, run it in a session with the
[RemoteSigned execution policy](https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_execution_policies).

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\run-tester.ps1
```

The launcher waits for Neo4j, builds the code graph and imports the facts, then
starts the app from the published images. It reads the reference checkout
through a read-only mount. Open <http://localhost:3000> once the frontend starts.
Choose `step-06` and ask **Where are the Product and Category endpoints
implemented in the Catalog service?** Look for source cards for
`ProductResource.java:28` and `CategoryResource.java:17`.

The API is on `localhost:8000` and Ollama is on `localhost:11434`. With Docker
Engine on Linux, the backend uses host networking and Neo4j also listens on
loopback port `7687`. Set `TESTER_NEO4J_PORT` before launch if that port is used
by another local database. On Docker Desktop, Neo4j stays on the internal
Compose network. Stop the launcher with `Ctrl+C`. It removes the containers and
temporary data volumes it created.

## Image tags and troubleshooting

The published image tag defaults to `develop`. For a release test, set
`SUNSETTRACKER_IMAGE_TAG` to the tag or `sha-…` published for that release.
Use a matching backend and frontend pair that includes the Graph integration
and this tester setup. For a local build, set both `SUNSETTRACKER_BACKEND_IMAGE`
and `SUNSETTRACKER_FRONTEND_IMAGE` to the already built image names before
running the launcher. [Container builds and publishing](Documentation/containers.md)

| Symptom | What to check |
| --- | --- |
| Reference checkout or a component is missing | Check the path and run the submodule initialization in step 2. |
| Image pull is denied | Sign in to GHCR with access to the team's packages and check the selected tag. |
| Import reports that the Python API or Git is missing | Use a prebuilt backend image that includes the graph pipeline and the tester setup. |
| A port is already in use | Stop the earlier app on port 3000 or 8000. On Linux, you can select a different Neo4j port using `TESTER_NEO4J_PORT`. |

## Development setup

To run the app from source, install [uv](https://docs.astral.sh/uv/getting-started/installation/),
Python 3.12 via `uv python install 3.12`, and [Node.js 22](https://nodejs.org/).
Use `ollama pull qwen3.5:2b` once before using the developer launchers.
The developer launchers are `./backend/run.sh` on Linux and
`.\backend\run.ps1` on Windows. The Windows developer launcher uses
[Windows Terminal](https://learn.microsoft.com/windows/terminal/install) and
[PowerShell 7](https://learn.microsoft.com/powershell/scripting/install/installing-powershell-on-windows).
See the [backend guide](backend/README.md) for commands and tests and the
[ingestion guide](backend/code-ingestion-pipeline/README.md) for manual imports.
