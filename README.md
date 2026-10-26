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

## Firebase emulators (local development)

Keep the FastAPI backend running locally (by default on port `8001`), then start
the Firestore and App Hosting emulators in their own terminal:

```powershell
./scripts/start-emulators.ps1
```

- App Hosting website: `http://localhost:5002`
- Firestore endpoint: `http://127.0.0.1:8080`
- Emulator UI: `http://127.0.0.1:4000`
- Project ID: `demo-crossword-arena`
- Local data and logs live under `.firebase/`, which is intentionally ignored by Git.

The App Hosting emulator runs the Next.js development server from `frontend/`
with `PORT=5002`. It uses the backend URL from `frontend/.env.local`. Firebase
Authentication, including Google sign-in, is not configured yet.

The normal frontend at `http://localhost:3000` is still available when running
`./scripts/start-dev.ps1`.

### Data flow

The frontend reads shared, public state from Firestore:

- Room list, room state, participants, and scoreboard are read with
  `onSnapshot` from `src/lib/roomsStore.ts` (Firestore emulator).
- Writes stay on FastAPI: join, submit, reveal, and admin actions still call
  the backend REST endpoints.
- The backend publishes a `rooms/{roomId}` snapshot to Firestore after every
  state change (`backend/app/services/firestore_publisher.py`).

Firestore is a read mirror of the in-memory FastAPI state. The backend remains
the source of truth for scoring and game rules.

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
