# Build Process Video — Narration Script (Deliverable 4.5)

**Files:** `build-process-video.mkv` / `build-process-video.mp4`  
**Runtime:** 03:09 · 1920×1080 · 30 fps · H.264 + AAC (−16 LUFS)  
**Voice:** neural TTS (Kokoro, voice `af_heart`), captions burnt in  
**Source footage:** Raihan's 8 screen recordings (C1–C8), trimmed, cropped to the relevant window, and time-compressed where marked on screen (e.g. “6× speed”).

---

### [00:00] Intro

> This is the build process for SunsetTracker: from a clean clone to a tested, containerised application, running locally and in CI.

### [00:10–00:31] 01 · Clone & checkout

> We start from a clean machine and clone the repository from GitHub.  
> Then we step into the project and check out the develop branch.  
> Git log confirms we're on the latest commit: the merge of pull request 115, which added our container build.  

Clip: C1

### [00:31–01:01] 02 · Backend tests

> For the backend, we delete the old virtual environment and let uv rebuild it from the lock file, so every dependency is pinned.  
> Pytest runs the API suite: 28 tests, all passing.  
> Next, the code-ingestion pipeline suite. It covers source loading, symbol extraction, graph relationships, and our shared data contracts.  
> 80 passed, one skipped, zero failures.  

Clip: C2

### [01:01–01:15] 03 · Frontend tests

> On the frontend, npm ci installs the exact versions from the lock file.  
> Then Vitest runs the component tests: five test files, seventeen tests, all green.  

Clip: C3

### [01:15–01:33] 04 · Docker build & run

> With every test green, one command builds and starts the whole stack: docker compose up, with the build flag.  
> Compose creates the network, starts the backend and frontend containers, and the backend server reports it's live on port 8000.  

Clip: C4

### [01:33–01:57] 05 · Smoke test

> In the browser, the backend health endpoint answers: status ok.  
> On localhost 3000, the SunsetTracker interface loads, and we send one of the verified inquiries.  
> The orchestrator answers, here with the built-in mock model, and lists the verified AST evidence behind it, linking legacy code to its migration status.  

Clip: C5

### [01:57–02:27] 06 · CI pipeline

> The same images are also built in CI.  
> The Container images workflow in GitHub Actions runs on every push to develop.  
> We re-run it on the latest commit.  
> It lints the Dockerfiles, then builds the backend and frontend images in parallel, and publishes them to the GitHub Container Registry.  
> About a minute later, sped up here, every job is green.  

Clip: C6

### [02:27–02:47] 07 · Documentation

> The .env example sets the ports and the backend URL, and shows how to point the backend at a real LLM, such as Ollama.  
> And containers.md documents the quick start, the Ollama setup, and every supported operating system and CPU architecture.  

Clip: C7

### [02:47–02:59] 08 · Teardown

> Finally, we stop the stack. Docker compose down removes both containers and the network.  
> And docker compose ps confirms nothing is left running.  

Clip: C8

### [02:59] Outro — “Build verified” summary

> That's the full cycle: clone, test, build, run, and tear down, locally and in CI. Thanks for watching.

---

**Edit notes:** the PowerShell `Remove-Item` error at the start of C3 and the blank Google tab at the start of C5 are cut. C2's ingestion run (66 s) and C6's CI run (≈1 min) are shown sped up, with a speed tag on screen.
