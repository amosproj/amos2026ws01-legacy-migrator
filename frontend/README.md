# SunsetTracker Frontend

**AI-Assisted Legacy Migration Knowledge Base — Web Application**  
*AMOS Winter Semester 2026/27 · Project 1 (iteratec)*

## Overview

The SunsetTracker frontend is a standalone, decoupled React application built with **Vite, React 19, TypeScript, and Tailwind CSS**. It fulfills the Presentation Tier specifications defined in the Sprint 2 Architecture Contract and the 28 October 2026 Industry Partner decisions:

1. **Chat Query Interface (`ChatUI`)**: Natural language queries answering key legacy-modernization questions (FR-06 through FR-09), complete with line-level GitHub source traceability and AST evidence cards.
2. **arc42 Views UI (`ViewsUI`)**: Interactive architecture views (System Context, Building Block View with status coloring, and Deployment View) rendered via Mermaid.

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
* **Backend Proxy:** The Vite development server automatically proxies `/api` requests to `http://127.0.0.1:8000`.
* **Graceful Standalone / Mock Fallback:** If the FastAPI backend is not running, the application seamlessly operates in offline mock mode, allowing full UI testing and demonstration of realistic migration inquiries.
* **Licensing Compliance:** Built entirely using permissive open-source packages (MIT / Apache-2.0 / BSD).

## Verification & Build

```bash
npm run typecheck
npm run build
```
