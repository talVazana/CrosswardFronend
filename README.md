# Crossword Collab

A real-time collaborative crossword puzzle game. Multiple players join a shared
room, fill in a crossword grid together, and watch scores update live.

## Overview

- **Backend**: Python FastAPI service (`backend/`) exposing a REST API for rooms,
  players, puzzle submissions, scoring, and live events. State is held in
  in-memory repositories.
- **Frontend**: Next.js (App Router) + React + TypeScript + Tailwind CSS
  (`frontend/`). Provides room join/play pages, an admin dashboard, and a
  puzzle editor.
- **E2E tests**: Playwright (`frontend/playwright.config.ts`).

## Installation

Install backend dependencies:

```powershell
pip install -r backend/requirements.txt
```

Install frontend dependencies:

```powershell
npm install --prefix frontend
```

## Startup (local development)

Start both the backend (uvicorn, `app.main:app --reload`) and the frontend
(`npm run dev`) with one script:

```powershell
./scripts/start-dev.ps1
```

This launches the backend on http://localhost:8000 and the frontend on
http://localhost:3000, and records the process IDs in
`scripts/dev-pids.json`.

Stop both processes:

```powershell
./scripts/stop-dev.ps1
```

## Testing

Run the full test suite (backend pytest + frontend vitest) with one script:

```powershell
./scripts/test.ps1
```

Individual suites:

```powershell
# Backend only (from backend/)
python -m pytest

# Frontend unit tests only (from frontend/)
npx vitest run

# Frontend E2E tests (Playwright, from frontend/)
npx playwright test
```
