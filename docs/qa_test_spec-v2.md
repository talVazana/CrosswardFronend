# Crossword Arena / Puzzle Room — AI Agent QA Test Specification (v2)

## Document Overview
This Quality Assurance Test Specification serves as the authoritative testing blueprint for automated AI agents and testing frameworks (such as Playwright and PyTest) executing end-to-end (E2E), API, and unit tests against the **Crossword Arena / Puzzle Room** application.

*Version 2 updates include test scenarios for the **Cross-Room Total Score System**, validating cumulative player score tracking, cross-room score persistence, and global leaderboard/roster displays.*

---

## 1. Global Test Execution Regulations & Setup

### 1.1 Test Environment & Isolation
1. **Local-Only Operations:** All tests must run strictly against local service instances. No external third-party dependencies or external parsers are permitted.
2. **Database Teardown & State Reset:** Every E2E test suite must trigger a full database reset endpoint (`POST /test/reset`) prior to execution to ensure complete test isolation and zero state pollution between runs. The reset must wipe ALL in-memory state: rooms, players, player identities, lifetime totals, scores, sessions, submissions, player clue states, public clue states, and the puzzle/answer repositories. A separate single-room JSON seed endpoint (`POST /e2e/seed`) is used to prepare a specific room and puzzle for a test without touching other rooms.
3. **Browser Context Separation:** To validate privacy and multi-user isolation, the AI test agent must instantiate isolated browser contexts for different roles:
   - `AdminContext`: Administrator browser context.
   - `Player1Context`: Primary player context ("Dana").
   - `Player2Context`: Secondary player context ("Amir").
   - `Player3Context`: Isolated/cross-room player context ("Lee").
4. **Deterministic Concurrency:** Millisecond race conditions and concurrency tie-breakers are evaluated at the backend API layer (`pytest` async handlers), while E2E tests focus on functional UI workflows.
5. **Automatic Color Assignment:** Player colors are assigned by the server when a player joins. There is NO manual color input in the UI. Colors follow a fixed palette in join order (Red, Teal, Amber, Purple, Pink, Orange, Olive, Blue) and are tied to the display name (identity) across all rooms. Tests must NOT attempt to set a color on the join form.

---

## 2. Test Suite Matrix

---

### Module 1: Room Creation, Admin Management & Lifecycle

#### TEST-ROOM-001: Admin Room Creation & Puzzle Import
- **Scenario Tested:** Admin creates a new game room and imports a puzzle.
- **Target Contexts:** `AdminContext`
- **Preconditions:** Database is reset to clean state (`POST /test/reset`).
- **Import Paths:**
  - Production: Admin uploads a puzzle image; the server runs the image parser to build the grid and clues.
  - Test seeding: `POST /e2e/seed` accepts a JSON puzzle fixture (`fixtures/puzzles/valid_sample_puzzle.json`) and official answers, creating a room directly without the image parser.
- **Test Steps:**
  1. Open application as Admin.
  2. Navigate to Admin Panel and click **Create Room**.
  3. Upload a local puzzle image and submit.
  4. Fill in Room Name ("Arena Alpha") and confirm.
  5. Inspect Admin Dashboard preview.
- **Success Criteria:**
  - Room "Arena Alpha" is created successfully and assigned a unique Room ID.
  - Puzzle grid preview, clues list (Across/Down), and clue numbers render accurately.
  - Initial Room Status is `Created` / `Pending`.
  - The `/e2e/seed` JSON path also creates a valid active room for downstream tests.

#### TEST-ROOM-002: Room Lifecycle Control (Start, Pause, Resume, Finish, Close)
- **Scenario Tested:** Admin controls room lifecycle states and verifies player submission enablement/blocking.
- **Target Contexts:** `AdminContext`, `Player1Context`
- **Preconditions:** Room "Arena Alpha" exists; Player 1 ("Dana") has joined Room "Arena Alpha".
- **Test Steps:**
  1. Admin clicks **Start Room**.
  2. Player 1 attempts to submit a clue answer -> Verify submission is accepted.
  3. Admin clicks **Pause Room**.
  4. Player 1 attempts to submit a clue answer while paused.
  5. Admin clicks **Resume Room**.
  6. Player 1 attempts to submit a clue answer again.
  7. Admin clicks **Finish Room**.
  8. Player 1 attempts to submit an answer after room finish.
- **Success Criteria:**
  - When room is `Paused`, UI disables the **Submit** button and backend API returns HTTP 400/409 error ("Room is paused").
  - When room is `Resumed`, submissions function normally.
  - When room is `Finished`, board enters read-only mode for players and no further points can be awarded.

#### TEST-ROOM-003: Admin Non-Player Status Enforcement
- **Scenario Tested:** Admin operates the room without receiving player attributes or participating in scoring.
- **Target Contexts:** `AdminContext`, `Player1Context`, `Player2Context`
- **Preconditions:** Room is active with Admin, Player 1, and Player 2 present.
- **Test Steps:**
  1. Inspect the live player roster on Player 1 and Player 2 UI screens.
  2. Admin approves/sets answers in Admin Dashboard.
  3. Check scoreboard and total score counts.
- **Success Criteria:**
  - Admin does NOT appear in the player roster.
  - Admin is assigned no player color (0 color index).
  - Admin score remains 0 and Admin cannot select cells or submit answers as a player.

---

### Module 2: Player Join & Room Isolation

#### TEST-JOIN-001: Player Join, Color Assignment & Session Re-entry
- **Scenario Tested:** Players join an active room, receive deterministic colors, and restore sessions upon re-entry.
- **Target Contexts:** `Player1Context` ("Dana"), `Player2Context` ("Amir")
- **Preconditions:** Room "Arena Alpha" is active.
- **Test Steps:**
  1. `Player1Context` accesses room link and enters name "Dana".
  2. `Player2Context` accesses room link and enters name "Amir".
  3. Verify color tags assigned to both players.
  4. `Player1Context` closes tab / reloads page, then enters name "Dana" again.
- **Success Criteria:**
  - Dana receives Color 1 (Red). Amir receives Color 2 (Teal).
  - Both players see each other in the live scoreboard/roster.
  - Re-entering as "Dana" restores the existing player session token without creating a duplicate player entry or resetting score.

#### TEST-JOIN-002: Multi-Room Isolation
- **Scenario Tested:** Players in separate rooms are fully isolated in active room state, board activity, and room-level chat/roster.
- **Target Contexts:** `Player1Context` ("Dana" in Room A), `Player3Context` ("Lee" in Room B)
- **Preconditions:** Admin creates Room A and Room B.
- **Test Steps:**
  1. Dana joins Room A. Lee joins Room B.
  2. Dana solves 1-Across in Room A.
  3. Inspect Lee's view in Room B.
- **Success Criteria:**
  - Dana is visible ONLY in Room A's active room player list.
  - Lee is visible ONLY in Room B's active room player list.
  - Room A board fills and active room score logs have ZERO effect on Room B's board or active room score.

---

### Module 3: Board Navigation, Keyboard Input & Private Drafts

#### TEST-UI-001: Grid Navigation, Direction Toggle & Black Cell Boundaries
- **Scenario Tested:** Player navigates grid cells using click and arrow keys, toggles Across/Down, and respects boundaries.
- **Target Contexts:** `Player1Context`
- **Preconditions:** Player 1 is inside an active puzzle room.
- **Test Steps:**
  1. Click an unassigned white grid cell -> Verify cell is selected and active clue is highlighted.
  2. Click the same cell again -> Verify direction toggles between Across and Down.
  3. Use arrow keys to navigate towards a black cell.
  4. Attempt to click a black cell.
- **Success Criteria:**
  - Black cells are completely unclickable and block keyboard cursor movement.
  - Selection highlights both the current cell and the entire associated clue strip.
  - Direction toggles correctly on intersecting white cells.

#### TEST-UI-002: Private Draft Isolation
- **Scenario Tested:** Player types unsubmitted letters into grid cells; drafts remain strictly private.
- **Target Contexts:** `Player1Context` ("Dana"), `Player2Context` ("Amir")
- **Preconditions:** Dana and Amir are in the same active room.
- **Test Steps:**
  1. Dana selects 1-Across and types draft letters ("APP..") without clicking Submit.
  2. Inspect Amir's screen and inspect API GET responses received by Amir's client.
- **Success Criteria:**
  - Dana sees her typed draft characters on her board.
  - Amir sees blank/empty cells for 1-Across.
  - Server websocket and REST payloads sent to Amir contain NO draft letter content from Dana.

---

### Module 4: Clue Solving, Submission & Scoring Rules

#### TEST-SCORE-001: First Solver (2 Pts) vs Subsequent Solver (1 Pt) & Color Locking
- **Scenario Tested:** First player to solve a clue earns 2 points and locks board color; second player earns 1 point.
- **Target Contexts:** `Player1Context` ("Dana"), `Player2Context` ("Amir")
- **Preconditions:** 1-Across official answer is "APPLE". Neither player has solved 1-Across.
- **Test Steps:**
  1. Dana selects 1-Across, types "APPLE", and clicks **Submit**.
  2. Check scoreboards for Dana and Amir.
  3. Inspect public grid representation for 1-Across on both clients.
  4. Amir selects 1-Across, types "APPLE", and clicks **Submit**.
  5. Check scoreboards again.
- **Success Criteria:**
  - Dana receives **+2 points** (First Solver).
  - 1-Across cells fill with Dana's color (Red) on ALL players' screens.
  - Amir submits correctly and receives **+1 point** (Subsequent Solver).
  - 1-Across cells remain locked to Dana's color (Red) publicly on the board.
  - Amir sees the solved text on his own board view, while other unsolved players see only the color block fill.

#### TEST-SCORE-002: Incorrect Submissions (0 Pts & Retry Behavior)
- **Scenario Tested:** Player submits an incorrect answer, earns 0 points, and can retry without penalty.
- **Target Contexts:** `Player1Context` ("Dana")
- **Preconditions:** 1-Across official answer is "APPLE".
- **Test Steps:**
  1. Dana types "APRIC" for 1-Across and submits.
  2. Verify error feedback and scoreboard.
  3. Dana immediately types "APPLE" and submits.
- **Success Criteria:**
  - Incorrect submission awards **0 points** and shows a transient error notification.
  - No rate limits, timeouts, or point penalties are imposed.
  - Subsequent correct submission ("APPLE") successfully awards **2 points**.

#### TEST-SCORE-003: Backend API Scoring Concurrency
- **Scenario Tested:** Simultaneous correct submissions for the same clue are evaluated atomically by the server.
- **Target Contexts:** PyTest Backend API Test (`CON-090`)
- **Preconditions:** Room active; 5 distinct player sessions authenticated.
- **Test Steps:**
  1. Dispatch 5 simultaneous asynchronous POST requests to `/rooms/{roomId}/clues/{clueId}/submissions` for clue 2-Down with correct answer "BANANA".
  2. Await all response promises and query database score log.
- **Success Criteria:**
  - Exactly **ONE** request receives a response payload granting 2 points (`is_first_solver: true`).
  - Remaining 4 requests receive response payloads granting 1 point (`is_first_solver: false`).
  - Total score sum across all 5 players in the room increased by exactly 6 points (2 + 1 + 1 + 1 + 1).

---

### Module 5: Admin Answer Setting, Pending Queue & Typo Adjustments

#### TEST-ADMIN-001: Pending Submission Queue (Missing Official Answer)
- **Scenario Tested:** Clue lacks pre-configured official answer; player submission enters Pending state.
- **Target Contexts:** `AdminContext`, `Player1Context` ("Dana")
- **Preconditions:** Clue 3-Down has no official answer set in the database.
- **Test Steps:**
  1. Dana selects 3-Down, enters "MANGO", and submits.
  2. Check Dana's UI status indicator for 3-Down.
  3. Inspect Admin Dashboard "Pending Submissions" list.
- **Success Criteria:**
  - Dana's submission is flagged as `Pending`.
  - Dana's score remains unchanged while pending.
  - Admin Dashboard displays Dana's submission ("MANGO" for 3-Down) in the review queue with timestamp.

#### TEST-ADMIN-002: Official Answer Setting & Automatic Retroactive Scoring
- **Scenario Tested:** Admin inputs official answer for a clue with pending guesses; system auto-evaluates queue.
- **Target Contexts:** `AdminContext`, `Player1Context` ("Dana"), `Player2Context` ("Amir")
- **Preconditions:** Dana submitted "MANGO" (Timestamp T1) and Amir submitted "MANGO" (Timestamp T2) for 3-Down while answer was missing.
- **Test Steps:**
  1. Admin opens Admin Panel, selects 3-Down, sets Official Answer to "MANGO", and saves.
  2. Inspect database score logs and client scoreboards.
- **Success Criteria:**
  - System automatically processes pending queue in chronological order (T1 then T2).
  - Dana automatically receives **+2 points** (First Solver).
  - Amir automatically receives **+1 point** (Subsequent Solver).
  - 3-Down grid cells fill with Dana's player color publicly.

#### TEST-ADMIN-003: Manual Admin Approval / Rejection
- **Scenario Tested:** Admin manually approves or rejects individual pending submissions.
- **Target Contexts:** `AdminContext`, `Player1Context` ("Dana")
- **Preconditions:** Dana submitted "LEMON" for 4-Across (Pending state).
- **Test Steps:**
  1. Admin opens Pending Queue and clicks **Reject** on Dana's guess.
  2. Verify Dana's view.
  3. Dana submits "ORANGE" for 4-Across (Pending state).
  4. Admin clicks **Approve** on Dana's guess.
- **Success Criteria:**
  - Rejected submission displays a brief "Rejected" toast notification on Dana's screen and allows retry.
  - Approved submission grants Dana **+2 points** and colors 4-Across with Dana's player color.

#### TEST-ADMIN-004: Admin Typo Correction & Public Ownership Permanence
- **Scenario Tested:** Admin corrects a typo in an official answer after points were awarded; public board color remains locked.
- **Target Contexts:** `AdminContext`, `Player1Context` ("Dana"), `Player2Context` ("Amir")
- **Preconditions:** Initial official answer was typo "APPEL". Dana submitted "APPEL" and earned 2 points + Red board fill.
- **Test Steps:**
  1. Admin updates official answer for 1-Across from "APPEL" to "APPLE".
  2. Amir submits "APPLE" for 1-Across.
  3. Check board color ownership and scores.
- **Success Criteria:**
  - Dana retains her original 2 points and the public board fill remains permanently Red (Dana's color).
  - Amir receives **+1 point** (or retroactive credit per audit log) for matching the corrected answer.
  - Public UI does NOT strip or transfer the public ownership color block from Dana.

---

### Module 6: Personal Answer Reveal & Good-Faith Mechanics

#### TEST-REVEAL-001: Personal Answer Reveal & Individual Ineligibility
- **Scenario Tested:** Player uses Reveal Answer on an unsolved clue, gains personal view, and loses scoring eligibility.
- **Target Contexts:** `Player1Context` ("Dana"), `Player2Context` ("Amir")
- **Preconditions:** 5-Across ("CHERRY") is unsolved by all players.
- **Test Steps:**
  1. Dana clicks **Reveal Answer** for 5-Across.
  2. Check Dana's grid view, Dana's score, and Dana's submit button state for 5-Across.
  3. Check Amir's grid view.
  4. Amir submits "CHERRY" for 5-Across.
- **Success Criteria:**
  - Dana sees solution "CHERRY" filled in her local board view.
  - Dana receives **0 points**.
  - Dana is marked **permanently ineligible** to score points for 5-Across (Submit button disabled or submissions rejected).
  - Amir's view remains unrevealed (blank).
  - Amir submits "CHERRY" and successfully earns **2 points** + public board color ownership.

#### TEST-REVEAL-002: Intersecting Letters (Free Letters) Good-Faith Behavior
- **Scenario Tested:** Player reveals an Across clue and uses intersecting letters to help solve Down clues.
- **Target Contexts:** `Player1Context` ("Dana")
- **Preconditions:** 1-Across intersects with 1-Down and 2-Down.
- **Test Steps:**
  1. Dana clicks **Reveal Answer** for 1-Across.
  2. Dana inspects intersecting grid cells for 1-Down and 2-Down.
  3. Dana types and submits correct answer for 1-Down.
- **Success Criteria:**
  - System allows Dana to submit 1-Down and awards points normally.
  - No penalties or cross-clue blocks are applied for using intersecting revealed letters (per Good-Faith policy).

---

### Module 7: Reconnection, State Persistence & Mobile UX

#### TEST-REC-001: Client Reconnect & State Restoration
- **Scenario Tested:** Player browser crashes or reloads mid-game; full state (points, solved clues, drafts) is restored.
- **Target Contexts:** `Player1Context` ("Dana")
- **Preconditions:** Dana has earned 3 points, solved 1-Across, and typed an unsubmitted draft into 2-Down.
- **Test Steps:**
  1. Hard refresh browser page (`Cmd+R` / `F5`) in `Player1Context`.
  2. Re-enter name "Dana" (or auto-resume session cookie).
- **Success Criteria:**
  - Scoreboard displays 3 points.
  - 1-Across shows as solved with previous color and letters.
  - Unsubmitted draft letters in 2-Down are restored to local view.

#### TEST-UI-003: Mobile Viewport Responsiveness
- **Scenario Tested:** Application functionality on mobile screen sizes (375x667 viewport).
- **Target Contexts:** Playwright Mobile Viewport Profile (`iPhone SE`)
- **Preconditions:** Room active.
- **Test Steps:**
  1. Emulate mobile screen resolution.
  2. Select clue, scroll clue lists, and open virtual/on-screen keyboard input.
  3. Submit answer.
- **Success Criteria:**
  - Grid scales dynamically without requiring horizontal window scrolling.
  - Clue list and submit controls remain fully accessible and visible.

---

### Module 8: Cross-Room Total Score System

#### TEST-TOTAL-001: Cross-Room Score Accumulation & Aggregation
- **Scenario Tested:** Player earns points in Room A, joins Room B, and earns points in Room B; total score aggregates across rooms.
- **Target Contexts:** `Player1Context` ("Dana")
- **Preconditions:** Admin creates Room A and Room B.
- **Test Steps:**
  1. Dana joins Room A and solves clues totaling **3 points** in Room A.
  2. Verify Dana's Room A scoreboard shows **3 points** (room score only; the lifetime total is NOT shown inside the room).
  3. Dana leaves Room A and joins Room B using her display name "Dana".
  4. Dana solves clues totaling **2 points** in Room B.
  5. Open the main view (home page) and inspect the lifetime score leaderboard for "Dana".
- **Success Criteria:**
  - Room B local scoreboard displays **2 points**.
  - The main-view lifetime leaderboard displays **5 points** for Dana (3 from Room A + 2 from Room B).
  - The total score API (`GET /players/Dana/total`) returns `totalScore = 5`.

#### TEST-TOTAL-002: Global Leaderboard & Total Score Visibility
- **Scenario Tested:** Players can view all players' overall cumulative scores across all rooms on the main-view lifetime leaderboard.
- **Target Contexts:** `Player1Context` ("Dana"), `Player2Context` ("Amir")
- **Preconditions:** Dana has earned 5 total points across Room A and Room B; Amir has earned 3 total points in Room A.
- **Test Steps:**
  1. Open the main view (home page) as Dana (`Player1Context`).
  2. Open the main view (home page) as Amir (`Player2Context`).
  3. Amir solves a clue in Room C for **+2 points** (raising his total to 5).
  4. Re-check the main-view leaderboard on both contexts.
- **Success Criteria:**
  - The leaderboard shows each player's color dot, name, and total (no rank index).
  - The leaderboard displays Dana (5 pts) and Amir (3 pts initially).
  - Leaderboard entries are sorted by total score descending.
  - When Amir earns points in Room C, his total updates to 5 on the leaderboard for both Dana and Amir within the refresh interval (the main view polls `GET /players/totals` every 15 seconds).

#### TEST-TOTAL-003: Session Identity & Persistent Score Mapping
- **Scenario Tested:** Player session re-entry maps to the correct player profile and retains total cumulative score.
- **Target Contexts:** `Player1Context` ("Dana")
- **Preconditions:** Dana has accumulated 10 total points across past rooms.
- **Test Steps:**
  1. Dana clears local session cache or switches browser tab, then re-enters the app and signs in with nickname "Dana" / session token.
  2. Fetch user profile payload and view total score widget.
- **Success Criteria:**
  - Player profile matches existing user record for "Dana".
  - Cumulative total score of 10 points is fully preserved.
  - Joining a brand new room retains the 10 total points as starting lifetime/aggregate total score.

---

### Module 9: Cross-Room Identity, Lifetime Persistence & Ordering

#### TEST-IDENTITY-001: Same Color in Every Room
- **Scenario Tested:** A player keeps one color across all rooms.
- **Target Contexts:** `Player1Context` ("Dana")
- **Preconditions:** Room A and Room B are active; reset state.
- **Test Steps:**
  1. Dana joins Room A and records her color.
  2. Dana joins Room B with the same display name.
  3. Compare colors.
- **Success Criteria:**
  - Dana's color in Room B equals her color in Room A.
  - `GET /rooms/{roomId}/me` returns the same `color` value for both rooms.

#### TEST-IDENTITY-002: One Browser in Many Rooms
- **Scenario Tested:** One browser session cookie holds a token per room, so a player can be in several rooms at once.
- **Target Contexts:** `Player1Context` ("Dana")
- **Preconditions:** Room A and Room B are active.
- **Test Steps:**
  1. Dana joins Room A in one tab.
  2. Dana joins Room B in a second tab of the same browser context.
  3. Submit an answer in Room A, then submit an answer in Room B.
- **Success Criteria:**
  - Both `GET /rooms/{roomId}/me` calls return 200 with distinct player ids.
  - Both submissions return 200.
  - The `Session-Token` cookie holds multiple tokens separated by `|` (one per room).

#### TEST-IDENTITY-003: Reclaim by Name Merges Duplicates
- **Scenario Tested:** Joining with an existing display name reuses the existing player instead of creating a duplicate.
- **Target Contexts:** `Player1Context` ("Dana")
- **Preconditions:** Dana already joined Room A.
- **Test Steps:**
  1. Clear cookies and join Room A again as "Dana" (case-insensitive).
- **Success Criteria:**
  - The join returns the same `playerId`.
  - The room player list still has exactly one "Dana".

#### TEST-TOTAL-004: Lifetime Total Survives Room Deletion
- **Scenario Tested:** A player's lifetime total is kept after the room is deleted.
- **Target Contexts:** `Player1Context` ("Dana")
- **Preconditions:** Dana earned 2 points in Room A.
- **Test Steps:**
  1. Record Dana's total via `GET /players/Dana/total`.
  2. Admin deletes Room A.
  3. Fetch Dana's total again.
- **Success Criteria:**
  - `GET /players/Dana/total` still returns the same total score.

#### TEST-TOTAL-005: Lifetime Total Survives Backend Restart
- **Scenario Tested:** Lifetime totals persist across a backend restart.
- **Target Contexts:** `Player1Context` ("Dana")
- **Preconditions:** Dana earned points; Firestore mirror is reachable.
- **Test Steps:**
  1. Record Dana's total.
  2. Restart the backend (no `--reload`).
  3. Fetch Dana's total again.
- **Success Criteria:**
  - The total is restored from Firestore and unchanged.

#### TEST-TOTAL-006: Newest-First Room Ordering
- **Scenario Tested:** Room cards on the main view are ordered newest first, top-left, wrapping down.
- **Target Contexts:** `AdminContext`
- **Preconditions:** Reset state.
- **Test Steps:**
  1. Create Room A, then Room B (later), then Room C (latest).
  2. Open the main view.
- **Success Criteria:**
  - The first card (top-left) is Room C, then Room B, then Room A.
  - Adding a new room pushes existing cards right, then wraps to the next row.

#### TEST-IDENTITY-004: Rejection Notice Shown Once Then Clears
- **Scenario Tested:** A rejected submission shows a notice that disappears once seen.
- **Target Contexts:** `AdminContext`, `Player1Context` ("Dana")
- **Preconditions:** Dana has a pending submission; admin rejects it.
- **Test Steps:**
  1. Admin rejects Dana's submission.
  2. Observe Dana's grid notice for the clue.
  3. Reload Dana's page.
- **Success Criteria:**
  - The clue shows a "Rejected" message for a few seconds.
  - After the message disappears, reloading does NOT show it again (seen marker by submission id).

---

### Module 10: Per-Room Statistics (Admin vs Players)

#### TEST-STAT-001: Statistics Button Opens a Modal on the Room Card
- **Scenario Tested:** A small Statistics button on each room card in the main view opens the room statistics without entering the room.
- **Target Contexts:** Any player context
- **Preconditions:** At least one room exists.
- **Test Steps:**
  1. Open the main view (home page).
  2. Click the **Statistics** button on a room card.
  3. Close the modal.
- **Success Criteria:**
  - A modal opens listing the room's statistics.
  - The user never navigates away from the main view.
  - The modal closes without changing the room.

#### TEST-STAT-002: Player Solved-Clue Count
- **Scenario Tested:** Each player's statistic counts one point per clue the player solved first.
- **Target Contexts:** `Player1Context` ("Dana"), `Player2Context` ("Amir")
- **Preconditions:** Dana solved 3 clues first; Amir solved 2 clues first.
- **Test Steps:**
  1. Open the Statistics modal for the room.
- **Success Criteria:**
  - Dana shows a count of 3.
  - Amir shows a count of 2.
  - Later solvers do not change the first solver's count.

#### TEST-STAT-003: Admin Solved-Clue Count
- **Scenario Tested:** The admin counts one point per clue he solved first; approving a player clue gives the admin zero.
- **Target Contexts:** `AdminContext`, `Player1Context`
- **Preconditions:** Admin solved 2 clues first; Dana submitted and the admin approved 1 clue.
- **Test Steps:**
  1. Open the Statistics modal for the room.
- **Success Criteria:**
  - Admin shows a count of 2.
  - The approved player clue credits Dana (1), not the admin.
  - Admin approval alone never increases the admin count.

#### TEST-STAT-004: Players Total vs Admin Row
- **Scenario Tested:** The modal shows a totals row comparing players against the admin.
- **Target Contexts:** Any player context
- **Preconditions:** Players solved 5 clues total; admin solved 2 clues total.
- **Test Steps:**
  1. Open the Statistics modal for the room.
- **Success Criteria:**
  - A "Players total" value of 5 and an "Admin" value of 2 are shown.
  - The two values are visually distinct.

#### TEST-STAT-005: Admin Excluded from Player Competition
- **Scenario Tested:** The admin appears only in the statistics panel, not in the player roster or lifetime leaderboard.
- **Target Contexts:** `AdminContext`, `Player1Context`
- **Preconditions:** Admin solved clues; the room has players.
- **Test Steps:**
  1. Inspect the player roster and lifetime leaderboard.
  2. Open the Statistics modal.
- **Success Criteria:**
  - Admin is absent from the player roster and lifetime leaderboard.
  - Admin appears only in the Statistics modal.

#### TEST-STAT-006: Admin Draft vs Submitted Indicator
- **Scenario Tested:** The admin grid shows which clues the admin has submitted (counts as solved) and which are still draft.
- **Target Contexts:** `AdminContext`
- **Preconditions:** Admin drafted one clue and submitted it; drafted a second clue without submitting.
- **Test Steps:**
  1. Open the admin room dashboard.
  2. Inspect the clue list and grid cells.
- **Success Criteria:**
  - The submitted clue is marked as submitted/solved.
  - The unsubmitted clue is marked as draft.
  - Only the submitted clue increases the admin statistic; the draft clue does not.

> **Implementation note:** the backend must record admin-first solves separately from "admin set an answer key". Drafting a clue stores nothing permanent. Admin submit records the clue as admin-solved (1 admin point) and marks the clue solved. A clue the admin solves first credits the admin; approving a pending player submission does not. The submitted-vs-draft state and the admin-first solve must be persisted so statistics survive restarts.

---

## 3. Test Execution Summary Checklist

| Module | Test ID | Description | Target Role | Pass Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **Room Management** | `TEST-ROOM-001` | Create Room & Import JSON | Admin | Room Created, Grid Rendered |
| **Room Management** | `TEST-ROOM-002` | Lifecycle (Pause/Resume/Finish) | Admin / Player | Submissions Blocked when Paused |
| **Room Management** | `TEST-ROOM-003` | Admin Non-Player Status | Admin / Player | No Color, 0 Score, Hidden from Roster |
| **Player Join** | `TEST-JOIN-001` | Join, Color & Re-entry | Player 1 & 2 | Unique Colors, Session Restored |
| **Player Join** | `TEST-JOIN-002` | Multi-Room Isolation | Player 1 & 3 | Zero Cross-Room State Leaks |
| **Board UI** | `TEST-UI-001` | Navigation & Boundaries | Player 1 | Black Cells Blocked, Direction Toggles |
| **Board UI** | `TEST-UI-002` | Private Draft Isolation | Player 1 & 2 | Drafts Invisible to Competitors |
| **Scoring** | `TEST-SCORE-001` | 1st (2pt) vs 2nd (1pt) Solver | Player 1 & 2 | 2pts First + Color Lock, 1pt Second |
| **Scoring** | `TEST-SCORE-002` | Incorrect Guesses & Retry | Player 1 | 0pts, Retries Allowed without Penalty |
| **Scoring** | `TEST-SCORE-003` | API Scoring Concurrency | Backend API | Exactly One 2pt Winner, Zero Dupes |
| **Admin Operations**| `TEST-ADMIN-001` | Pending Submission Queue | Admin / Player | Guesses Queued when Answer Missing |
| **Admin Operations**| `TEST-ADMIN-002` | Answer Setting & Auto-Score | Admin / Players | Chronological Auto-Scoring |
| **Admin Operations**| `TEST-ADMIN-003` | Admin Manual Approval/Reject | Admin / Player | Correct Toast Feedback & Score Award |
| **Admin Operations**| `TEST-ADMIN-004` | Admin Typo Correction | Admin / Players | Color Ownership Remains Locked |
| **Personal Reveal** | `TEST-REVEAL-001` | Reveal & Ineligibility | Player 1 & 2 | 0pts, Player Ineligible, Others Eligible |
| **Personal Reveal** | `TEST-REVEAL-002` | Intersecting Letter Rules | Player 1 | Good-Faith Intersecting Use Allowed |
| **UX & Hardening** | `TEST-REC-001` | Reconnect & Restoration | Player 1 | Scores, Solves & Drafts Restored |
| **UX & Hardening** | `TEST-UI-003` | Mobile Viewport Layout | Mobile Player | Responsive Grid, No Horiz Scroll |
| **Total Score System**| `TEST-TOTAL-001`| Cross-Room Score Accumulation | Player 1 | Room Scores Sum into Lifetime Total |
| **Total Score System**| `TEST-TOTAL-002`| Global Leaderboard Visibility | Player 1 & 2 | All Players See Global Scores Live |
| **Total Score System**| `TEST-TOTAL-003`| Session Identity & Persistence | Player 1 | Cumulative Total Retained on Re-entry |
| **Identity & Persistence** | `TEST-IDENTITY-001` | Same Color in Every Room | Player 1 | Color Identical Across Rooms |
| **Identity & Persistence** | `TEST-IDENTITY-002` | One Browser in Many Rooms | Player 1 | Multi-Token Cookie, Both Submissions OK |
| **Identity & Persistence** | `TEST-IDENTITY-003` | Reclaim by Name Merges Duplicates | Player 1 | Same Player ID, No Duplicate |
| **Identity & Persistence** | `TEST-TOTAL-004` | Total Survives Room Deletion | Player 1 | Total Unchanged After Delete |
| **Identity & Persistence** | `TEST-TOTAL-005` | Total Survives Backend Restart | Player 1 | Total Restored From Firestore |
| **Identity & Persistence** | `TEST-TOTAL-006` | Newest-First Room Ordering | Admin | Newest Card Top-Left |
| **Identity & Persistence** | `TEST-IDENTITY-004` | Rejection Notice Shown Once | Admin / Player | Notice Clears After Seen |
| **Room Statistics** | `TEST-STAT-001` | Statistics Modal on Card | Player | Modal Opens Without Entering Room |
| **Room Statistics** | `TEST-STAT-002` | Player Solved-Clue Count | Player 1 & 2 | 1 Per First-Solved Clue |
| **Room Statistics** | `TEST-STAT-003` | Admin Solved-Clue Count | Admin / Player | Approving Gives Admin 0 |
| **Room Statistics** | `TEST-STAT-004` | Players Total vs Admin | Player | Totals Row Shown |
| **Room Statistics** | `TEST-STAT-005` | Admin Excluded from Competition | Admin / Player | Admin Only in Statistics |
| **Room Statistics** | `TEST-STAT-006` | Admin Draft vs Submitted Indicator | Admin | Draft Does Not Count Until Submit |
