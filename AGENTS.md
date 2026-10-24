# AGENTS.md

## Project stack

- **Backend**: FastAPI (Python), served with uvicorn (`uvicorn app.main:app --reload`)
- **Frontend**: Next.js (App Router) with React, TypeScript, and Tailwind CSS
- **Testing**: pytest (backend), vitest (frontend unit tests), Playwright (frontend E2E tests)

## Status

The baseline implementation is complete. Rooms, live updates, scoring,
submissions, and the admin dashboard are implemented end to end.

## Local development

- Start everything: `./scripts/start-dev.ps1`
- Stop everything: `./scripts/stop-dev.ps1`
- Run all tests: `./scripts/test.ps1`

See README.md for full installation, startup, and testing instructions.
