# Crossword Arena — Autonomous AI Agent Build Plan

**Document purpose:** A complete, implementation-oriented specification for an autonomous coding agent to build and verify a competitive crossword website. Treat this file as the project's primary build contract unless the repository already contains newer, explicit requirements from the owner.

## 1. Product goal

Build a hobby, non-commercial competitive crossword web application with two interfaces:

- **Player view:** enter a room, solve a crossword, submit answers, see participants and scores, and optionally reveal answers privately to oneself.
- **Administrator panel:** create and manage rooms, import/edit crossword puzzles, maintain official answers, and control room lifecycle.

The app must be useful locally before any production deployment. Prefer free, local-first tools and avoid paid services unless the owner explicitly approves them.

## 2. Rules for the coding agent

1. Start by inspecting the repository, Git status, existing docs, package files, and existing implementation. Do not overwrite or discard user work.
2. If the repository already has an established stack, preserve it unless a documented blocker requires a change. Record the decision in `docs/DECISIONS.md`.
3. Implement one milestone/feature branch at a time. Do not attempt the entire application in one enormous change.
4. Run relevant tests, linting, and type checks before declaring a feature complete. Never claim a command passed unless it was actually run and its exit status checked.
5. Keep frontend and backend code in separate directories.
6. Use fixtures and a mock parser adapter until the owner supplies the existing image-parser URL and exact response schema. Do not invent a real parser API contract.
7. Keep secrets out of source control. Provide `.env.example` with placeholders only.
8. Do not add AI answer-solving, web crawling, scraping, analytics, paid APIs, or production deployment unless explicitly requested.
9. Make all security-sensitive decisions on the server, including permissions, answer validation, scoring, and reveal eligibility.
10. Update `docs/WORK_LOG.md` after every milestone with changes, commands run, results, issues, and the next step.
11. If a required external service, credential, schema, or remote is missing, isolate it behind an adapter and continue with a tested local implementation.
12. Do not silently change the game rules in this document. If a conflict with existing user-approved documentation is found, document it and ask the owner to resolve the conflict.

## 3. Repository structure

Adapt to the current repository if it already has a sensible structure. Otherwise use this target layout:

```text
/
  AGENTS.md
  README.md
  .gitignore
  .env.example
  docs/
    WORK_LOG.md
    DECISIONS.md
    TEST_PLAN.md
    API_CONTRACT.md
    USER_GUIDE.md
  frontend/
    package.json
    src/
    public/
    tests/
  backend/
    pyproject.toml
    app/
      main.py
      api/
      core/
      models/
      repositories/
      services/
      adapters/
    tests/
  fixtures/
    puzzles/
    parser-responses/
    scenarios/
  scripts/
    start-dev.ps1
    stop-dev.ps1
    test.ps1
    seed-local.ps1
    reset-local.ps1
```

### Suggested stack

- **Frontend:** Next.js App Router, TypeScript, Tailwind CSS.
- **Backend:** Python, FastAPI, Pydantic.
- **Persistence:** use the repository's existing Firebase/Firestore emulator setup if one exists and works locally. Otherwise use a small local persistence implementation behind repository interfaces. Do not couple game rules directly to a particular database.
- **Testing:** pytest for backend; frontend unit/component tests using the test runner already present or Vitest; Playwright for end-to-end flows where practical.
- **Quality:** Ruff for Python; ESLint and TypeScript checks for frontend; Prettier if already adopted.

Do not install every suggested tool automatically. First inspect the repository and choose the smallest compatible toolset.

## 4. Scope

### Included in the first complete version

- Player room entry and stable identity for the current session.
- Multiple independent rooms.
- Crossword grid and clue selection.
- Keyboard entry and navigation.
- Private player drafts before submission.
- Submission and official-answer validation.
- Scoring and score history.
- Public solved-clue state that does not automatically reveal letters.
- Per-player answer reveal.
- Admin dashboard and room lifecycle controls.
- Puzzle import/editor using an adapter for the existing parser.
- Local development scripts, fixtures, tests, and documentation.
- Responsive and accessible UI, including Hebrew/right-to-left support where text is Hebrew.

### Explicitly out of scope unless requested

- AI-generated answers or AI solving.
- Crawling websites or automatically discovering puzzles.
- Production hosting/deployment and paid infrastructure.
- Payments, ads, subscriptions, public social network features, or analytics.
- Rebuilding the owner's existing Render image parser.
- Any claim that real-time multi-device behavior is complete until it has been implemented and tested.

## 5. Roles, identity, and permissions

### Administrator

- One site-wide administrator role.
- Can create, edit, start, pause, resume, finish, and close rooms.
- Can import and edit puzzle structure and official answers.
- Can inspect submissions and resolve explicitly documented administrative cases.
- Does not earn points.

The initial local development environment may use a clearly documented development-only admin identity. Never ship a hard-coded production password or secret. Production authentication must be designed before deployment.

### Player

- Joins a room using the room's intended entry mechanism.
- Has a stable player ID for that room/session, a display name, and a chosen or assigned color.
- Can reconnect without accidentally creating duplicate identities when a valid session token exists.
- Can keep draft answers private until submitted.
- Can see public room status, participants, scores, and publicly solved-clue state.
- Can reveal an official answer privately for their own view, subject to the rules below.

### Authorization rules

- A player must not access another room's private data by changing a room ID.
- A player must not read official answers before the game's reveal rules permit it.
- A player must not read another player's drafts or private reveal state.
- Client-supplied points, timestamps, player IDs, admin flags, and correctness claims are untrusted.
- Enforce permissions in backend services and API handlers, not only by hiding UI controls.

## 6. UI and visual design

Create a clean, competitive, playful interface with the crossword grid as the main focus. Avoid an oversized hero section and avoid a heavy, nearly black background with aggressive orange accents. Use restrained forging/competition motifs only as subtle visual details; keep readability and puzzle-solving usability primary. Do not add a person image. A logo/image may be supplied by the owner later; use a neutral placeholder until then.

### Player screen

- Header: room title, room status, connection/reconnection indicator.
- Main area: responsive crossword grid.
- Clue panel: selected clue text, clue number, direction, answer length if known, and answer-entry state.
- Room panel: participant list, colors, live scores, and solved status.
- Clear distinction between the selected clue, the player's current draft, a submitted answer, and a solved clue.
- Mobile layout must remain usable without requiring horizontal scrolling across the whole page. The grid may have its own scroll/zoom behavior when necessary.

### Grid states

Represent cell states distinctly and accessibly:

- Black/non-playable cell.
- Empty playable cell.
- Currently selected cell.
- Cells belonging to the selected clue.
- Cells filled in the current player's private draft.
- Locked/accepted letters where the game rules require them.
- Publicly solved clue state, with solver/ownership color where applicable.
- Private answer-revealed state for the current player.

Do not use color alone to communicate state; add outlines, labels, icons, or accessible descriptions where practical.

### Numbering

Use clue numbers from the parser's normalized puzzle data. A cell can start both an Across and a Down clue and must display one shared number. Do not independently renumber the puzzle in the UI if the parser supplies numbering. If the parser does not supply numbers, numbering must be computed once in a documented normalization layer and covered by tests.

## 7. Puzzle model and parser integration

The owner has an existing Python image-parser service hosted on Render. Integrate it; do not rebuild it. The actual URL and response schema will be supplied separately.

### Adapter requirements

Create a parser adapter with a stable internal interface, for example:

- `parse_image(input) -> ParsedPuzzle`
- `normalize_parser_response(raw) -> ParsedPuzzle`
- `validate_puzzle(puzzle) -> ValidationReport`

The exact function signatures can match the existing codebase. The adapter must:

- Have a fixture/mock mode that works without network access.
- Apply a bounded timeout to external requests.
- Return clear, safe errors for timeout, invalid JSON, invalid schema, and invalid puzzle structure.
- Validate dimensions, cell count, clue references, numbering, and answer lengths where the data makes these checks possible.
- Preserve raw parser output for admin inspection during import, without exposing it to players unless needed.
- Never silently guess missing official answers.
- Make it possible to swap parser implementation without changing room, scoring, or UI code.

### Suggested normalized puzzle structure

This is an internal design proposal, **not a claim about the current parser's actual JSON schema**. Map the real parser output to this model after the owner provides it.

```json
{
  "puzzleId": "example-puzzle",
  "title": "Example Crossword",
  "width": 5,
  "height": 5,
  "cells": [
    {"row": 0, "col": 0, "type": "white", "number": 1, "startsAcross": true, "startsDown": true},
    {"row": 0, "col": 1, "type": "white", "number": null, "startsAcross": false, "startsDown": false}
  ],
  "clues": [
    {"clueId": "A1", "number": 1, "direction": "across", "text": "Example clue", "answerLength": 5},
    {"clueId": "D1", "number": 1, "direction": "down", "text": "Example clue", "answerLength": 5}
  ]
}
```

Store official answers separately from public puzzle structure. On room creation, snapshot the chosen puzzle version so later edits to the source puzzle do not unexpectedly mutate an active room.

### Admin import workflow

1. Admin selects an image or uses a fixture in development.
2. The adapter invokes the parser or fixture provider.
3. Admin reviews the grid, numbering, clues, and any extracted metadata.
4. Admin corrects structure and enters/verifies official answers.
5. Validation reports missing or inconsistent data.
6. Admin explicitly saves a puzzle version.
7. A room uses an immutable snapshot of that version.

## 8. Grid interaction and answer entry

- Clicking/tapping a playable cell selects it.
- Clicking the same cell again may switch Across/Down when both directions exist; provide a visible direction toggle too.
- Selecting a clue highlights all its cells and shows its clue text.
- Typing a letter writes into the current player's draft and advances according to the selected direction.
- Backspace removes the current letter or moves backward according to a consistent, tested behavior.
- Navigation must not enter black cells or continue beyond the selected answer boundary.
- Support keyboard navigation and touch interaction.
- Normalize user input consistently for the puzzle language (for example, trim surrounding whitespace and apply documented case normalization). Do not remove meaningful characters without a rule.
- A draft is private to the player until submitted. Other players must not see it.
- The frontend may offer immediate visual feedback, but only the server determines correctness and points.

## 9. Submission, solving, and scoring rules

These rules are authoritative unless the owner supplies a newer explicit correction.

1. The first eligible player to submit a correct answer for a clue earns **2 points**.
2. Each subsequent eligible player who submits that clue correctly earns **1 point**.
3. An incorrect submission earns **0 points** and may be retried.
4. A player may earn points for a given clue at most once.
5. The administrator earns **0 points**.
6. The server determines submission timestamps and correctness. Do not trust client timestamps or client-reported scores.
7. Correct-answer evaluation and score allocation must be atomic/idempotent so concurrent submissions cannot both be treated as first solver.
8. Publicly marking a clue as solved does not automatically reveal its letters to every player.
9. A player who has personally revealed the answer is no longer eligible to score for that clue. Other players remain eligible if they have not revealed it themselves and have not already scored for it.
10. If an answer has not yet been entered/saved by the administrator, submissions for that clue remain pending. When the official answer is saved, evaluate pending submissions in original server timestamp order. The first eligible correct submission gets 2 points; later eligible correct submissions get 1 point. Incorrect ones get 0 and may be retried.
11. If a room is finished while pending submissions exist, require an explicit administrative reconciliation step or a documented rule; do not silently discard pending submissions.
12. Record score changes as append-only score events or equivalent auditable records. Avoid deriving historical score only from mutable client state.

### Clarification on public solved state

The first successful solver may establish the clue's public solved/ownership color. Later players can still submit the same correct answer for the subsequent-solver point if otherwise eligible. Do not change the first-solver ownership color merely because a later player also solves the clue.

### Example

- Dana submits a correct answer first: Dana gets 2 points and the clue becomes publicly solved with Dana's ownership color.
- Amir submits the same correct answer later and is eligible: Amir gets 1 point; the ownership color remains Dana's.
- Lee submits a wrong answer: Lee gets 0 and may retry.
- If Dana reveals the answer before solving it, Dana is ineligible to score for that clue; Amir and Lee remain independently eligible under the rules.

### Server-side scoring transaction

Implement scoring in a single backend service and transaction boundary. The operation must check, as applicable:

- Room is active and submissions are allowed.
- Player belongs to the room and is not an administrator.
- Clue belongs to the room's puzzle snapshot.
- Official answer exists; otherwise store pending submission.
- Player has not revealed the answer for this clue.
- Player has not already received a score for this clue.
- The answer matches the normalized official answer.
- Whether any eligible correct score event already exists for the clue.
- Score event, per-player clue state, public solved state, and score totals are updated consistently.

Use a database transaction or equivalent concurrency-safe mechanism. Add a unique/idempotency key for each submission request so retries caused by network problems cannot award duplicate points.

## 10. Room lifecycle

Recommended states:

- `draft`: room is being configured and is not visible to players.
- `lobby`: players can join; solving is not yet enabled.
- `active`: submissions and scoring are enabled.
- `paused`: submissions are temporarily disabled; drafts should be preserved.
- `finished`: no new scoring submissions; show final scores and results.
- `closed`: archived and no longer joinable.

Enforce allowed transitions on the server. Document how pending submissions are handled during pause/finish. A finished or closed room must not accept new score events. Room data and IDs must be isolated from all other rooms.

## 11. Data model and persistence boundaries

Use names appropriate to the chosen database, but preserve these logical entities:

- **Rooms:** room ID, title, status, puzzle snapshot/version, creator, timestamps, settings.
- **Players:** room ID, player ID, display name, color, joined/last-seen timestamps, role within the room.
- **Sessions:** securely managed reconnect/session data; store tokens safely and do not expose them in public room responses.
- **Puzzle versions:** dimensions, cell layout, clues, parser metadata, validation state.
- **Official answers:** clue ID and normalized answer; restricted to admin/server workflows.
- **Submissions:** submission ID, room ID, player ID, clue ID, answer, server timestamp, status (`pending`, `correct`, `incorrect`, or equivalent), scoring result.
- **Player clue state:** per-player draft, personal reveal state, and whether the player already scored for the clue.
- **Public clue state:** solved status and first-solver ownership/color, separate from private letters.
- **Score events:** immutable or append-only records of awarded points and reason.
- **Audit events:** important admin changes and reconciliation actions.

### Data separation

Public player responses must never contain official answers or another player's draft. Prefer separate repositories/documents or explicit response DTOs for public room state and restricted answer data. Do not serialize database objects directly to the browser.

### Repository interfaces

Put persistence behind interfaces such as `RoomRepository`, `PuzzleRepository`, `PlayerRepository`, `SubmissionRepository`, and `ScoreRepository`. Tests should be able to use in-memory/fake repositories. Do not make the UI or scoring engine depend directly on Firestore-specific data structures.

## 12. API design

Use REST endpoints or the repository's existing API style. Keep endpoint naming consistent and document request/response schemas in `docs/API_CONTRACT.md`. Suggested route families:

### Health and development

- `GET /health` — backend liveness only; do not leak secrets or internal configuration.
- `GET /ready` — optional readiness check for configured local dependencies.

### Player routes

- `POST /rooms/{roomId}/join`
- `GET /rooms/{roomId}/state`
- `GET /rooms/{roomId}/puzzle/public`
- `GET /rooms/{roomId}/clues/{clueId}` — public clue details only.
- `PUT /rooms/{roomId}/clues/{clueId}/draft`
- `POST /rooms/{roomId}/clues/{clueId}/submissions`
- `POST /rooms/{roomId}/clues/{clueId}/reveal`
- `GET /rooms/{roomId}/scores`

### Admin routes

- `POST /admin/rooms`
- `PATCH /admin/rooms/{roomId}`
- `POST /admin/rooms/{roomId}/start`
- `POST /admin/rooms/{roomId}/pause`
- `POST /admin/rooms/{roomId}/resume`
- `POST /admin/rooms/{roomId}/finish`
- `POST /admin/rooms/{roomId}/close`
- `POST /admin/puzzles/parse` — parser adapter/fixture mode.
- `POST /admin/puzzles`
- `PATCH /admin/puzzles/{puzzleId}`
- `PUT /admin/puzzles/{puzzleId}/clues/{clueId}/answer`
- `GET /admin/rooms/{roomId}/submissions`
- `POST /admin/rooms/{roomId}/reconcile-pending`

These are suggested boundaries, not a mandate to create every endpoint before it is needed. Build only the routes required by the current milestone and test their authorization.

### API response rules

- Use explicit Pydantic request and response models.
- Return structured, safe errors with stable error codes.
- Do not return stack traces, raw credentials, session tokens, or official answers in player-facing errors.
- Validate all IDs and input lengths.
- Add pagination for potentially large admin submission/audit lists if needed.
- Keep the public room-state response limited to data a player is allowed to see.

## 13. Administrator experience

Build the admin panel in small increments.

### Room dashboard

- List rooms with title, status, creation time, and player count.
- Create a room from a validated puzzle version.
- Start, pause, resume, finish, and close rooms with confirmation for destructive or irreversible actions.
- Inspect current participants, scores, and pending submissions.
- Never allow accidental edits to an active room's puzzle snapshot.

### Puzzle editor/import review

- Preview grid and clues.
- Show missing answers and structural validation errors.
- Edit clue text and official answer.
- Save a new puzzle version rather than mutating a version already used by an active room.
- Provide a clear warning before changing an answer that has already affected scoring. If such a change is allowed, require an explicit audit/reconciliation path.

### Admin safety

- Keep admin-only routes protected server-side.
- Confirm irreversible lifecycle actions.
- Log answer changes, manual score adjustments, pending reconciliation, and room closure.
- Do not provide silent manual score editing. Any adjustment must create an audit/score event with a reason.

## 14. Live updates and reconnect behavior

Implement basic request/refresh behavior first; add WebSockets, Server-Sent Events, or a Firebase realtime listener only after the core state model and tests are stable.

When live updates are added:

- Broadcast public state only to authorized room members.
- Never broadcast private drafts or official answers.
- On reconnect, fetch an authoritative room snapshot from the server.
- Handle duplicate, delayed, or out-of-order client events safely.
- Display a connection indicator and a useful retry action.
- Preserve a player's unsent draft locally or server-side as appropriate, but do not confuse a saved draft with a submitted answer.

## 15. Test strategy

Tests are a required part of implementation, not a final optional phase.

### Backend unit tests

- Input normalization and answer comparison.
- Puzzle validation and numbering normalization.
- Room transition rules.
- Eligibility checks for submissions and reveal.
- First-solver/subsequent-solver scoring.
- Duplicate request/idempotency handling.
- Pending submissions and chronological reconciliation.
- Room isolation and permissions.

### Backend integration tests

- API request validation and safe error responses.
- Repository persistence and transactions.
- Public DTOs exclude official answers, private drafts, session secrets, and other players' reveal state.
- Concurrent submissions cannot award multiple first-solver scores.
- Admin routes reject player identities.

### Frontend tests

- Grid rendering, shared clue numbering, selection, direction switching, typing, backspace, and boundaries.
- Draft/submission/reveal states are visually distinct.
- Responsive layouts and keyboard accessibility.
- Error, loading, empty, paused, finished, and disconnected states.

### End-to-end tests

Use a deterministic seeded puzzle and local services. Avoid dependence on a live external parser or paid service. The E2E suite should cover the full scenario in Section 16.

## 16. Mandatory acceptance scenarios

Each scenario must have an automated test where practical and a manual test note where automation is not practical.

**A. Join and reconnect** — A player joins a room, receives a stable identity, reloads/reconnects, and does not create a duplicate participant when using the same valid session.

**B. Grid numbering** — A cell starting both Across and Down displays one number and allows selection of either clue.

**C. Input boundaries** — Typing advances correctly and never crosses a black cell or the selected answer's boundary.

**D. Private drafts** — Player A's draft is not present in Player B's API response or UI.

**E. First correct answer** — The first eligible correct submission receives exactly 2 points and establishes public solved/ownership state.

**F. Subsequent correct answer** — A second eligible player receives exactly 1 point; the original ownership color remains unchanged.

**G. Wrong answer and retry** — An incorrect answer receives 0 points and can be retried; the retry does not create duplicate score events.

**H. Personal reveal** — Revealing an answer changes only that player's reveal state and view. That player cannot later score for the clue; other eligible players can.

**I. Missing official answer** — A submission made before the admin saves an official answer remains pending and is evaluated in original server timestamp order after the answer is saved.

**J. Concurrent correct submissions** — Concurrent eligible correct submissions produce one first-solver award of 2 points and subsequent eligible awards of 1 point, with no duplicate scoring.

**K. Room lifecycle** — Submissions are accepted only when allowed by the room state. Pausing preserves drafts; finishing prevents new score events.

**L. Room isolation** — A player from Room A cannot read or change Room B state by altering IDs or requests.

**M. Admin permissions** — Player identities cannot create rooms, edit official answers, change room state, or reconcile submissions.

**N. Parser adapter** — Fixture mode produces a valid normalized puzzle. Invalid schemas and timeouts return clear errors and do not corrupt saved puzzles.

**O. Responsive/accessibility** — The core solving flow works on desktop and mobile, and key controls can be used with a keyboard.

## 17. End-to-end demonstration scenario

Build a deterministic local test demonstrating this sequence:

1. Admin creates a puzzle called `Friday Crossword` from a fixture and enters the official answers.
2. Admin creates a room and moves it to `lobby`.
3. Dana, Amir, and Lee join with different display colors.
4. Admin starts the room.
5. Dana drafts an answer; other players cannot see it.
6. Dana submits a correct answer first and receives 2 points.
7. Amir submits the same correct answer and receives 1 point; the public ownership color remains Dana's.
8. Lee submits a wrong answer, receives 0 points, edits the draft, and retries.
9. For another clue without an official answer, a player submits and the submission becomes pending.
10. Admin saves that official answer; pending submissions are processed in original server timestamp order.
11. A player reveals a clue privately; only their view changes and they become ineligible to score for that clue.
12. Admin pauses and resumes the room; unsent drafts are preserved.
13. Admin finishes the room; no further score events can be created.
14. Reload/reconnect and verify room state, scores, and privacy boundaries.
15. Run the test suite and record the actual results in `docs/WORK_LOG.md`.

## 18. Git and feature-branch workflow

The owner wants local-first development and a separate feature branch per feature/milestone, with changes merged and pushed only after verification.

### Before the first change

- Inspect `git status`, current branch, remotes, recent commits, and existing branch conventions.
- Never overwrite uncommitted user changes.
- Do not invent a Git remote or push to an unknown repository.
- Check `.gitignore` for `.env`, credentials, build artifacts, virtual environments, local databases, logs, and generated files.
- Create or update `AGENTS.md` with concise project-specific instructions.

### Suggested feature branches

Use the repository's established naming convention if one exists. Otherwise:

1. `feature/001-project-scaffold`
2. `feature/002-local-backend-health`
3. `feature/003-puzzle-domain-model`
4. `feature/004-player-room-join`
5. `feature/005-crossword-grid-ui`
6. `feature/006-clue-selection-and-input`
7. `feature/007-private-drafts`
8. `feature/008-submission-validation`
9. `feature/009-scoring-engine`
10. `feature/010-personal-answer-reveal`
11. `feature/011-admin-room-dashboard`
12. `feature/012-admin-puzzle-editor`
13. `feature/013-parser-adapter`
14. `feature/014-live-updates-and-reconnect`
15. `feature/015-end-to-end-tests`
16. `feature/016-accessibility-responsive-polish`

### Required steps for each feature

1. Ensure the working tree is understood and user changes are preserved.
2. Start from the latest verified base branch available locally. Fetch first if a configured remote exists and network access is available.
3. Create the feature branch.
4. Implement one coherent feature with focused changes.
5. Add or update tests.
6. Run targeted tests, full relevant regression tests, linting, and type checks.
7. Inspect `git diff` and `git status`; remove secrets and unrelated changes.
8. Update docs and `docs/WORK_LOG.md`.
9. Commit with a concise, descriptive message.
10. If a remote is configured and pushing is authorized/available, push the feature branch and verify the push result.
11. Merge only after required checks pass. Prefer the repository's existing merge policy; do not force-push.
12. Run smoke/regression checks on the merged branch.
13. Push the updated base branch only if a remote is configured and this is authorized.
14. Confirm the final working tree and report any unpushed local commits or unresolved issues.

If tests fail, fix the problem or clearly document the blocker. Do not merge a known-broken feature merely to advance the milestone.

## 18A. Linked test specifications (required)

The build plan is part of a connected English-language specification set. Keep these documents synchronized whenever a milestone, use case, or rule changes:

- [`crossword_arena_milestone_test_matrix.md`](crossword_arena_milestone_test_matrix.md) — unit, component, API, integration, security, parser, and concurrency tests mapped to milestones.
- [`crossword_arena_e2e_use_case_tests.md`](crossword_arena_e2e_use_case_tests.md) — browser-driven use cases, visible UI assertions, multi-user scenarios, and evidence requirements.
- [`crossword_arena_test_strategy_and_scenarios.md`](crossword_arena_test_strategy_and_scenarios.md) — overall test principles and reporting policy.

A milestone is not complete based only on code implementation. Its mapped tests must actually run, with outcomes recorded as PASS, FAIL, BLOCKED, or SKIPPED. See the two linked test specifications for exact gates.

## 19. Milestones and acceptance gates

### Milestone 0 — Repository inspection and plan alignment

- Inspect repository and existing docs.
- Confirm frontend/backend structure and available local services.
- Record actual stack, constraints, and missing external inputs.
- Create/update `AGENTS.md`, `README.md`, `docs/DECISIONS.md`, and `docs/WORK_LOG.md` as appropriate.

**Gate:** No user work lost; baseline status and commands documented; no invented remote or credentials.

### Milestone 1 — Local project skeleton

- Ensure frontend and backend start independently.
- Add backend `/health` endpoint.
- Add a minimal frontend page showing backend connectivity or a clear offline state.
- Add install/start/test scripts for the current OS, including PowerShell if the owner uses Windows.

**Gate:** Both services start locally using documented commands; health endpoint and frontend smoke test pass.

### Milestone 2 — Domain models and deterministic fixtures

- Define puzzle, clue, cell, room, player, submission, score-event, and state models.
- Add a small fixture puzzle with answers stored separately.
- Implement puzzle validation and normalization.

**Gate:** Model and validation tests pass; no assumptions about the real parser schema leak into the domain model.

### Milestone 3 — Persistence and room isolation

- Implement repository interfaces and a local adapter.
- Persist rooms, players, puzzle snapshots, and submissions as appropriate.
- Ensure every query is scoped to authorized room/player context.

**Gate:** Integration tests prove persistence and room isolation. If Firebase emulator is used, document exact startup requirements.

### Milestone 4 — Player join and lobby

- Join room, display name/color, participant list, stable session/reconnect behavior.
- Lobby and room status UI.

**Gate:** Join/reconnect scenario passes; duplicate joins are handled consistently.

### Milestone 5 — Crossword board UI

- Render black and white cells, numbering, selection, clue list, responsive layout.
- Support a cell shared by Across and Down clues.

**Gate:** Grid tests pass with fixture data; no accidental client-side renumbering.

### Milestone 6 — Clue selection and keyboard input

- Direction switching, typing, backspace, navigation, boundary handling, touch selection.

**Gate:** All input and boundary scenarios pass on desktop; basic mobile behavior is manually verified or automated.

### Milestone 7 — Private drafts

- Save and restore player drafts.
- Ensure drafts are never returned to other players.

**Gate:** Privacy tests pass at API and UI level.

### Milestone 8 — Submission and official-answer workflow

- Submit answer to server.
- Admin maintains official answers.
- Store pending submissions when an official answer is missing.

**Gate:** Correctness is server-side; missing-answer submissions are not discarded or guessed.

### Milestone 9 — Scoring engine and concurrency

- Implement atomic first/subsequent solver scoring.
- Add idempotency, score events, and chronological pending reconciliation.

**Gate:** Scoring unit, integration, and concurrency tests pass; no duplicate awards.

### Milestone 10 — Personal answer reveal

- Reveal an answer only for the requesting player.
- Prevent that player from earning points for that clue afterward.

**Gate:** Reveal privacy and eligibility tests pass for multiple players.

### Milestone 11 — Admin room dashboard and lifecycle

- Create/list/manage rooms.
- Start, pause, resume, finish, close.
- View participants, scores, and pending submissions.

**Gate:** Server-side admin authorization and lifecycle transition tests pass.

### Milestone 12 — Puzzle editor and parser adapter

- Import fixture data through adapter.
- Build review/edit/save workflow.
- Integrate the real Render parser only after URL and schema are supplied.

**Gate:** Fixture mode works offline; validation errors are visible; active rooms retain immutable puzzle snapshots.

### Milestone 13 — Live updates and reconnect

- Add a suitable realtime mechanism only if needed and compatible with the repository.
- Reconcile authoritative server state on reconnect.

**Gate:** No private data leaks through broadcasts; duplicate/out-of-order events do not corrupt state.

### Milestone 14 — End-to-end tests and hardening

- Automate the end-to-end demonstration scenario.
- Review authorization, input validation, race conditions, errors, and data exposure.

**Gate:** E2E flow and regression suite pass; known gaps are documented honestly.

### Milestone 15 — UX, accessibility, and documentation

- Responsive polish, keyboard accessibility, empty/loading/error states.
- Complete README and user/developer instructions.
- Verify clean setup from a fresh checkout where possible.

**Gate:** A new developer can start the project and run tests using the documentation.

## 20. Local developer experience

Provide simple scripts and document the actual commands supported by the selected stack. Prefer one command per common action, but do not hide errors behind scripts that always exit successfully.

Document commands for:

- Installing frontend dependencies.
- Creating/activating the Python virtual environment and installing backend dependencies.
- Starting any required local emulator.
- Starting backend and frontend in separate terminals, plus an optional combined launcher.
- Loading deterministic seed data.
- Running backend tests.
- Running frontend tests and E2E tests.
- Running lint and type checks.
- Stopping local processes and resetting local data safely.

PowerShell scripts should work on Windows if that is the development environment. If a script is not tested on Windows, state that clearly rather than claiming support.

## 21. Security and privacy checklist

- [ ] No secrets or `.env` files committed.
- [ ] Admin permissions enforced by backend.
- [ ] Official answers absent from public player responses.
- [ ] Player drafts private to their owner.
- [ ] Personal reveal state private to the player.
- [ ] Room IDs cannot be used to bypass membership checks.
- [ ] Client-supplied points and timestamps ignored for authoritative scoring.
- [ ] Score mutations are atomic and idempotent.
- [ ] Inputs have length/type limits and safe error handling.
- [ ] Parser/network calls have timeouts and validated responses.
- [ ] Admin answer edits and score reconciliation are audited.
- [ ] Finished/closed rooms cannot accept new scoring events.
- [ ] Logs do not expose passwords, tokens, official answers, or private drafts.

## 22. Definition of done

A feature is complete only when:

- It meets its acceptance criteria.
- Relevant tests exist and pass.
- Relevant lint/type checks pass.
- Authorization and privacy implications are reviewed.
- Loading, error, and empty states are handled where applicable.
- Documentation and work log are updated.
- The diff contains no unrelated changes or secrets.
- The branch is committed; push/merge status is accurately reported.
- Any limitations are stated explicitly.

The full website is complete only when the end-to-end scenario passes, the app can be started from documented local commands, all mandatory acceptance scenarios are covered, and unresolved limitations are listed.

## 23. Work-log template

Append an entry for each milestone:

```markdown
## YYYY-MM-DD — Milestone N: Short name

- Branch:
- Goal:
- Implemented:
- Tests/commands run:
- Results:
- Known issues/blockers:
- Commit:
- Push/merge status:
- Next milestone:
```

Record real commands and outcomes. Do not use placeholders in a completed entry.

## 24. Inputs expected from the owner later

The agent should proceed with fixtures and adapters until these are available:

1. The crossword image or representative sample image.
2. The existing Render parser URL and any required request format.
3. The parser's real response JSON/schema, preferably with one representative successful response and one error response.
4. The intended Git remote, if pushing is desired and no remote is already configured.
5. Any final visual assets/logo.

Do not block unrelated development while waiting for these inputs.

## 25. First action for the agent

Start with **Milestone 0**. Inspect the existing repository and preserve all user changes. Then implement the smallest verified local skeleton or continue the existing project from its actual state. Work feature-by-feature, run tests before merging, and keep `docs/WORK_LOG.md` truthful and current. Use fixture data until the real parser contract is supplied. Never fabricate test results, API behavior, repository state, or deployment success.






# Appendix: Edge Cases and Product Owner Decisions

**Purpose:** During the design and architecture review, several edge cases, potential exploits, and edge-case collisions were identified. Because this is a low-intensity, non-commercial hobby project intended for friends and family, the Product Owner has explicitly decided to favor simplicity over complex, over-engineered protections. 

The Master Agent and Dev Agent must adhere to these decisions and **avoid building unnecessary anti-cheat mechanisms or complex conflict resolutions.**

## 1. Intersecting Reveals (Free Letters)
* **The Identified Risk:** If a player uses the "Personal Reveal" feature on a long Across clue, they gain the intersecting letters for multiple Down clues. They lose eligibility for the Across clue, but could theoretically use the revealed letters to easily solve the Down clues for points.
* **Product Owner Decision:** **Approved / No Action Required.** 
* **Implementation Directive:** Do not build complex logic to penalize players for using intersecting letters. The game relies on good faith. A player only loses point eligibility for the specific clue they clicked "Reveal" on.

## 2. Multiple Pending Submissions
* **The Identified Risk:** If an official answer is missing (Pending state), and a player submits multiple different guesses before the admin updates the answer, there could be a conflict over which submission to evaluate.
* **Product Owner Decision:** **Approved / Unlimited Retries.**
* **Implementation Directive:** There is no limit on the number of attempts a player can make. The system should simply evaluate submissions as they come in or process the most recent/relevant pending submission once the admin provides the answer. Keep the logic straightforward.

## 3. Brute-Force Guessing / Spamming
* **The Identified Risk:** Players receive 0 points for a wrong answer but can retry instantly. A player could spam random letter combinations on a short word until they guess it correctly, bypassing the mental challenge.
* **Product Owner Decision:** **Ignored / Trust the Players.**
* **Implementation Directive:** This is a hobby game, not a commercial product. Do NOT implement rate-limiting, timeouts, penalty point deductions, or CAPTCHAs. Assume players act in good faith.

## 4. Revoking Public Ownership (Admin Typo Corrections)
* **The Identified Risk:** If an admin typos an official answer (e.g., "APPEL"), and a player submits that typo, they get 2 points and the public ownership color. If the admin later corrects the answer to "APPLE", the system would normally need complex UI logic to strip the color from the first player and award it to someone else.
* **Product Owner Decision:** **First is First / Keep the Color.**
* **Implementation Directive:** The first person to successfully match the active official answer gets the 2 points and their color permanently locks on the public board. If an admin later corrects a typo, retroactive points (+1) can be awarded to others based on the audit log, but do NOT build UI logic to revoke or change the public ownership color on the board.

## 5. Exact Timestamp Collisions (Tie-Breakers)
* **The Identified Risk:** If two players submit the exact same correct answer at the exact same millisecond, the system needs a deterministic tie-breaker to decide who gets 2 points and who gets 1 point.
* **Product Owner Decision:** **Out of Scope / Low Probability.**
* **Implementation Directive:** Because this is a low-traffic, low-intensity application where rooms live for a few hours or days, the mathematical probability of a true millisecond collision is negligible. Do not over-engineer a complex tie-breaker mechanism. Simply rely on the natural chronological processing order of the backend/database.