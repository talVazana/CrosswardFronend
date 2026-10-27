# Crossword Arena — Unified Test Matrix & E2E Scenarios

**Purpose:** This document is the single source of truth for the QA Agent and Master Orchestrator. It replaces all previous test strategy and scenario documents. It maps Unit, API, and E2E Browser scenarios directly to project Milestones.

## 1. Global Testing Rules (Read First)
1. **Local Only:** All tests must run locally. There is NO external Render parser dependency. Puzzles are imported strictly via a local `fixture_puzzle.json`.
2. **State Reset (Teardown):** Every E2E browser scenario MUST begin with a database reset (e.g., calling a `/test/reset` endpoint or script) to ensure a clean state. Tests must not corrupt each other.
3. **No UI Concurrency Testing:** Do not attempt to test millisecond race conditions using Playwright. Concurrency and tie-breakers are tested strictly at the API/Backend level.
4. **No Meta-Testing:** Do not deliberately fail tests just to test the reporting system.
5. **Role Separation:** Use separate Playwright browser contexts for Admin, Player 1 (Dana), and Player 2 (Amir) to prove data privacy.

---

## 2. Milestone Test Mapping

The Master Agent will instruct the QA Agent to execute the tests listed under each Milestone.

### M1: Local Project Skeleton
* **API-001:** `GET /health` returns 200 OK.
* **E2E-001 (Smoke):** Start the app locally; the main page renders without console errors.

### M2: Domain Models & Local JSON Fixture
* **UT-010:** Validate `fixture_puzzle.json` maps correctly to the puzzle domain model.
* **UT-011:** Reject malformed JSON missing required grid/clue fields.

### M3 & M4: Persistence, Player Join, and Lobby
* **IT-030:** Create, read, and update a room in the local database.
* **E2E-002 (Join & Isolate):** 
  * *Setup:* Reset DB. Admin creates Room A.
  * *Steps:* Dana joins Room A. Amir joins Room A. Lee joins Room B.
  * *Assert:* Dana and Amir see each other in Room A. Lee is completely isolated in Room B.

### M5 & M6: Crossword Board UI & Keyboard Input
* **CT-050:** Board rendering—black cells are unclickable, clue numbering matches the JSON.
* **E2E-003 (Interact & Navigate):**
  * *Steps:* Dana selects an Across clue. Types letters. Uses backspace. Attempts to navigate into a black cell.
  * *Assert:* Direction switches correctly on shared cells. Black cells block typing. Boundaries are respected.

### M7: Private Drafts
* **E2E-004 (Draft Privacy):**
  * *Steps:* Dana types a partial answer (draft) but does not submit.
  * *Assert:* Dana sees her draft. Amir (in a separate browser context) sees empty cells. API responses to Amir do not contain Dana's draft letters.

### M8 & M9: Submission, Scoring, & Concurrency
* **UT-080 / UT-090:** Backend logic: First correct = 2 pts. Subsequent correct = 1 pt. Wrong = 0 pts.
* **CON-090 (API Concurrency):** Send 5 simultaneous correct API submissions for the same clue. Assert exactly ONE submission gets 2 points, others get 1 point. No duplicate scoring.
* **E2E-005 (Gameplay Loop):**
  * *Setup:* Reset DB. Load JSON puzzle.
  * *Steps:* Dana submits correct answer -> gets 2 points, clue turns Dana's color. Amir submits same correct answer -> gets 1 point, color stays Dana's. Lee submits wrong answer -> gets 0 points, retries correctly -> gets 1 point.

### M10: Personal Answer Reveal
* **E2E-006 (Personal Reveal):**
  * *Steps:* Dana clicks "Reveal" for 1-Across.
  * *Assert:* Dana sees the answer. Amir does not see the answer. Dana attempts to submit 1-Across and is rejected (ineligible). Amir submits 1-Across and earns points.

### M11: Admin Room Dashboard & Lifecycle
* **API-110:** Reject player attempts to call `POST /admin/rooms/{id}/finish`.
* **E2E-007 (Room Lifecycle):**
  * *Steps:* Admin pauses the room. Dana attempts to submit an answer.
  * *Assert:* Dana's UI disables submission. The backend rejects the submission with a "room paused" error. Admin finishes room -> no further points can be awarded.

### M12: Puzzle Editor (Local Import)
* **E2E-008 (Admin JSON Import):**
  * *Steps:* Admin uploads `fixture_puzzle.json`.
  * *Assert:* Admin preview shows the grid, clues, and numbers correctly before officially opening the room.

### M13: Live Updates & Reconnect
* **E2E-009 (Reconnect state):**
  * *Steps:* Dana earns 2 points and writes a draft. Dana reloads the page (simulating reconnect).
  * *Assert:* Dana's identity, 2 points, and local draft are fully restored.

### M14 & M15: Hardening & Final UX
* **E2E-010 (Pending Submissions / Admin Typo Fix):**
  * *Steps:* Admin creates a room but leaves 1-Across answer empty. Dana submits "APPLE". 
  * *Assert:* Submission is "Pending". 
  * *Steps:* Admin adds official answer "APPLE". 
  * *Assert:* Dana is retroactively awarded 2 points automatically.
* **E2E-011 (Accessibility & Mobile):**
  * *Steps:* Run Playwright on a mobile viewport profile.
  * *Assert:* The board does not require horizontal page scrolling; inputs remain visible and clickable.

---

## 3. QA Agent Instructions
1. For every milestone completion requested by the Master Agent, execute the corresponding tests listed above.
2. For Unit/API tests, use `pytest`.
3. For E2E tests, use `playwright test`.
4. If a test fails, provide the CLI error output directly back to the Master/Dev Agent.
5. Do NOT mark a milestone as PASS unless the corresponding E2E and API tests return a strict success exit code (0).