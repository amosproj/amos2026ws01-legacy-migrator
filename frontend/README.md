# SunsetTracker Frontend

**AI-Assisted Legacy Migration Knowledge Base — Web Application**  
*AMOS Winter Semester 2026/27 · Project 1 (iteratec)*

## Overview

The SunsetTracker frontend is a standalone, decoupled React application built with **Vite, React 19, TypeScript, and Tailwind CSS**. It fulfills the Presentation Tier specifications defined in the Sprint 2 Architecture Contract and the 28 October 2026 Industry Partner decisions:

1. **Chat Query Interface (`ChatUI`)**: Natural language queries answering key legacy-modernization questions (FR-06 through FR-09), complete with line-level GitHub source traceability and AST evidence cards.
2. **arc42 Views UI (`ViewsUI`)**: Interactive architecture views (System Context, Building Block View with status coloring, and Deployment View) rendered via Mermaid.
3. **Git Comparisons (`DiffUI`)**: A GitHub-first workflow for selecting a repository, choosing base/head branches from dropdowns, and reviewing changed-file explanations, risk, and migration warnings.

## Quick Start

```bash
cd frontend
./start.sh
```

Or manually:

```bash
cd frontend
npm install
npm run dev
```

The application runs at **`http://localhost:3000`**.

## Architecture & Integration

* **Decoupled Deployment:** Frontend and Backend are hosted independently.
* **Backend Proxy:** Both the Vite development server (`npm run dev`) and the
  preview server (`npm run preview`) proxy `/api` requests to
  `http://127.0.0.1:8000`.
* **Streaming Chat:** Chat answers are streamed from the backend as
  newline-delimited JSON and rendered token by token; a Stop button cancels
  long-running generations. Connection and LLM errors are shown in the chat.
* **Illustrative Evidence:** Source evidence cards are illustrative mock data
  for the demonstrator until the ingestion pipeline provides real evidence.
  The arc42 views are likewise rendered from mock view definitions.
* **Licensing Compliance:** Built entirely using permissive open-source packages (MIT / Apache-2.0 / BSD).

## Verification & Build

```bash
npm run typecheck
npm run build
```
