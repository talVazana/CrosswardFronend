import pytest
from fastapi.testclient import TestClient

import jwt

import app.services.scoring_service as scoring_service
from app.api.routes import admin as admin_module
from app.api.routes import drafts as drafts_module
from app.api.routes import gameplay as gameplay_module
from app.api.routes import rooms as rooms_module
from app.api.routes import submissions as submissions_module
from app.main import app
from app.models.answers import OfficialAnswers
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import ASSIGNED_PLAYER_COLORS, Player, Room, RoomStatus
from app.repositories.in_memory import (
    InMemoryAnswerRepository,
    InMemoryPlayerClueStateRepository,
    InMemoryPlayerRepository,
    InMemoryRoomRepository,
    InMemoryScoreRepository,
    InMemorySubmissionRepository,
)
from app.services.scoring_service import ScoringService

ROOM_ID = "flow-room"
PUZZLE_ID = "flow-puzzle"
CLUE_ID = "A1"
ANSWER = "APPLE"
PLAYER_A = "player-a"
PLAYER_B = "player-b"
ADMIN = "admin-1"
TOKEN_A = "token-a"
TOKEN_B = "token-b"


def make_puzzle() -> Puzzle:
    return Puzzle(
        puzzleId=PUZZLE_ID,
        title="Flow Puzzle",
        width=1,
        height=1,
        cells=[
            Cell(
                row=0,
                col=0,
                type="white",
                number=1,
                startsAcross=True,
                startsDown=False,
            )
        ],
        clues=[
            Clue(
                clueId=CLUE_ID,
                number=1,
                direction="across",
                text="Fruit",
                answerLength=5,
            )
        ],
    )


def make_room() -> Room:
    return Room(
        roomId=ROOM_ID,
        title="Flow Room",
        status=RoomStatus.active,
        puzzleSnapshot=make_puzzle(),
        creatorId=ADMIN,
    )


def make_player(player_id: str, color: str, role: str = "player") -> Player:
    return Player(
        roomId=ROOM_ID,
        playerId=player_id,
        displayName=player_id,
        color=color,
        role=role,
    )


@pytest.fixture
def env(monkeypatch):
    room_repository = InMemoryRoomRepository()
    room_repository.create(make_room())

    player_repository = InMemoryPlayerRepository()
    player_repository.add(make_player(PLAYER_A, ASSIGNED_PLAYER_COLORS[0]))
    player_repository.add(make_player(PLAYER_B, ASSIGNED_PLAYER_COLORS[1]))
    player_repository.add(make_player(ADMIN, "#000000", role="admin"))

    answer_repository = InMemoryAnswerRepository()
    submission_repository = InMemorySubmissionRepository()
    clue_state_repository = InMemoryPlayerClueStateRepository()
    score_service = ScoringService(InMemoryScoreRepository())

    monkeypatch.setattr(rooms_module, "room_repository", room_repository)
    monkeypatch.setattr(rooms_module, "player_repository", player_repository)
    monkeypatch.setattr(
        rooms_module,
        "_sessions",
        {TOKEN_A: (ROOM_ID, PLAYER_A), TOKEN_B: (ROOM_ID, PLAYER_B)},
    )
    monkeypatch.setattr(admin_module, "answer_repository", answer_repository)
    monkeypatch.setattr(submissions_module, "answer_repository", answer_repository)
    monkeypatch.setattr(gameplay_module, "answer_repository", answer_repository)
    monkeypatch.setattr(
        submissions_module, "submission_repository", submission_repository
    )
    monkeypatch.setattr(submissions_module, "_clue_locks", {})
    monkeypatch.setattr(
        drafts_module, "player_clue_state_repository", clue_state_repository
    )
    monkeypatch.setattr(
        gameplay_module, "player_clue_state_repository", clue_state_repository
    )
    monkeypatch.setattr(drafts_module, "_player_clue_states", clue_state_repository.states)
    monkeypatch.setattr(scoring_service, "_default_service", score_service)

    with TestClient(app, base_url="https://testserver") as client:
        yield {
            "client": client,
            "answer_repository": answer_repository,
            "submission_repository": submission_repository,
            "score_service": score_service,
        }


def as_player(client: TestClient, token: str) -> None:
    client.cookies.set(rooms_module.SESSION_COOKIE_NAME, token)


def as_admin(client: TestClient) -> None:
    token = jwt.encode(
        {"email": "shachar383838@gmail.com"}, "test-secret", algorithm="HS256"
    )
    response = client.post(
        "/admin/session", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text


def submit(client: TestClient, token: str, answer: str = ANSWER):
    as_player(client, token)
    return client.post(
        f"/rooms/{ROOM_ID}/clues/{CLUE_ID}/submissions",
        json={"answer": answer},
    )


def approve(client: TestClient, answer: str = ANSWER):
    as_admin(client)
    response = client.put(
        f"/admin/puzzles/{PUZZLE_ID}/clues/{CLUE_ID}/answer",
        json={"answer": answer},
    )
    assert response.status_code == 200, response.text


def public_state(client: TestClient) -> dict:
    response = client.get(f"/rooms/{ROOM_ID}/state")
    assert response.status_code == 200, response.text
    return response.json()


def progress(client: TestClient, token: str) -> dict:
    as_player(client, token)
    response = client.get(f"/rooms/{ROOM_ID}/player-progress")
    assert response.status_code == 200, response.text
    return response.json()


def test_admin_grid_state_has_puzzle_answers_and_solved_colors_but_no_admin_player(env):
    client = env["client"]
    approve(client)

    response = client.get(f"/admin/rooms/{ROOM_ID}")
    assert response.status_code == 200, response.text
    state = response.json()

    assert state["puzzle"]["puzzleId"] == PUZZLE_ID
    assert state["officialAnswers"] == {CLUE_ID: ANSWER}
    assert state["solvedClues"] == []
    assert {player["id"] for player in state["players"]} == {PLAYER_A, PLAYER_B}


def test_admin_preapproval_makes_first_player_two_points_and_later_player_one(env):
    client = env["client"]
    approve(client)

    first = submit(client, TOKEN_A, "apple")
    second = submit(client, TOKEN_B, "APPLE")

    assert first.json() == {"status": "correct", "points": 2}
    assert second.json() == {"status": "correct", "points": 1}

    state = public_state(client)
    assert state["solvedClues"] == [
        {"clueId": CLUE_ID, "firstSolverColor": ASSIGNED_PLAYER_COLORS[0]}
    ]


def test_pending_submission_is_approved_manually_and_admin_grid_fills_with_first_solver(env):
    client = env["client"]

    pending = submit(client, TOKEN_A)
    assert pending.json() == {"status": "pending"}

    as_admin(client)
    admin_state = client.get(f"/admin/rooms/{ROOM_ID}").json()
    pending_entries = admin_state["pendingSubmissions"]
    assert len(pending_entries) == 1
    assert pending_entries[0]["submissionId"]
    assert {
        key: pending_entries[0][key] for key in ("clueId", "playerId", "answer")
    } == {"clueId": CLUE_ID, "playerId": PLAYER_A, "answer": ANSWER}

    approve(client)
    stored = env["submission_repository"].list_pending_by_room(ROOM_ID)
    assert stored == []

    admin_state = client.get(f"/admin/rooms/{ROOM_ID}").json()
    assert admin_state["officialAnswers"] == {CLUE_ID: ANSWER}
    assert admin_state["solvedClues"] == [
        {"clueId": CLUE_ID, "firstSolverColor": ASSIGNED_PLAYER_COLORS[0]}
    ]

    public = client.get(f"/rooms/{ROOM_ID}/state")
    assert public.json()["solvedClues"] == [
        {"clueId": CLUE_ID, "firstSolverColor": ASSIGNED_PLAYER_COLORS[0]}
    ]
    assert ANSWER not in public.text


def test_public_state_never_exposes_approved_solution(env):
    client = env["client"]
    approve(client)

    response = client.get(f"/rooms/{ROOM_ID}/state")

    assert ANSWER not in response.text
    assert "officialAnswers" not in response.json()


def test_admin_can_reject_pending_submission_without_scoring(env):
    client = env["client"]
    assert submit(client, TOKEN_A).json() == {"status": "pending"}

    as_admin(client)
    pending = client.get(f"/admin/rooms/{ROOM_ID}").json()["pendingSubmissions"]
    assert len(pending) == 1
    submission_id = pending[0]["submissionId"]

    response = client.post(
        f"/admin/rooms/{ROOM_ID}/submissions/{submission_id}/reject"
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "rejected",
        "clueId": CLUE_ID,
        "playerId": PLAYER_A,
    }
    assert client.get(f"/admin/rooms/{ROOM_ID}").json()["pendingSubmissions"] == []
    assert public_state(client)["solvedClues"] == []
    assert progress(client, TOKEN_A) == {
        "solved": [],
        "revealed": [],
        "answers": {},
        "pending": [],
        "rejected": [
            {"clueId": CLUE_ID, "submissionId": submission_id},
        ],
    }


def test_rejection_clears_after_player_resubmits(env):
    client = env["client"]
    assert submit(client, TOKEN_A).json() == {"status": "pending"}

    as_admin(client)
    pending = client.get(f"/admin/rooms/{ROOM_ID}").json()["pendingSubmissions"]
    url = f"/admin/rooms/{ROOM_ID}/submissions/{pending[0]['submissionId']}/reject"
    assert client.post(url).status_code == 200
    assert [item["clueId"] for item in progress(client, TOKEN_A)["rejected"]] == [CLUE_ID]

    assert submit(client, TOKEN_A, "APPLE").json() == {"status": "pending"}
    assert progress(client, TOKEN_A)["rejected"] == []


def test_rejecting_same_submission_twice_returns_conflict(env):
    client = env["client"]
    assert submit(client, TOKEN_A).json() == {"status": "pending"}

    as_admin(client)
    pending = client.get(f"/admin/rooms/{ROOM_ID}").json()["pendingSubmissions"]
    submission_id = pending[0]["submissionId"]
    url = f"/admin/rooms/{ROOM_ID}/submissions/{submission_id}/reject"

    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 409


def test_rejecting_unknown_submission_returns_not_found(env):
    client = env["client"]
    as_admin(client)

    response = client.post(f"/admin/rooms/{ROOM_ID}/submissions/submission-missing/reject")

    assert response.status_code == 404


def test_revealed_player_earns_zero_and_later_solver_becomes_first_solver(env):
    client = env["client"]
    approve(client)

    as_player(client, TOKEN_A)
    reveal = client.post(f"/rooms/{ROOM_ID}/clues/{CLUE_ID}/reveal")
    assert reveal.status_code == 200, reveal.text
    assert reveal.json() == {"answer": ANSWER}

    revealed_solver = submit(client, TOKEN_A)
    assert revealed_solver.json() == {"status": "correct", "points": 0}
    assert public_state(client)["solvedClues"] == []

    later = submit(client, TOKEN_B)
    assert later.json() == {"status": "correct", "points": 2}
    assert public_state(client)["solvedClues"] == [
        {"clueId": CLUE_ID, "firstSolverColor": ASSIGNED_PLAYER_COLORS[1]}
    ]


def test_player_progress_tracks_only_that_players_solved_and_revealed_clues(env):
    client = env["client"]
    approve(client)

    assert submit(client, TOKEN_A).json()["status"] == "correct"
    assert progress(client, TOKEN_A) == {
        "solved": [CLUE_ID],
        "revealed": [],
        "answers": {CLUE_ID: ANSWER},
        "pending": [],
        "rejected": [],
    }
    assert progress(client, TOKEN_B) == {
        "solved": [],
        "revealed": [],
        "answers": {},
        "pending": [],
        "rejected": [],
    }

    as_player(client, TOKEN_B)
    reveal = client.post(f"/rooms/{ROOM_ID}/clues/{CLUE_ID}/reveal")
    assert reveal.status_code == 200, reveal.text

    assert progress(client, TOKEN_B) == {
        "solved": [],
        "revealed": [CLUE_ID],
        "answers": {CLUE_ID: ANSWER},
        "pending": [],
        "rejected": [],
    }
    assert progress(client, TOKEN_A) == {
        "solved": [CLUE_ID],
        "revealed": [],
        "answers": {CLUE_ID: ANSWER},
        "pending": [],
        "rejected": [],
    }


def test_pending_submission_counts_as_solved_only_after_admin_approval(env):
    client = env["client"]

    pending = submit(client, TOKEN_A)
    assert pending.json() == {"status": "pending"}
    assert progress(client, TOKEN_A) == {
        "solved": [],
        "revealed": [],
        "answers": {CLUE_ID: ANSWER},
        "pending": [CLUE_ID],
        "rejected": [],
    }

    approve(client)

    assert progress(client, TOKEN_A) == {
        "solved": [CLUE_ID],
        "revealed": [],
        "answers": {CLUE_ID: ANSWER},
        "pending": [],
        "rejected": [],
    }


def test_hebrew_final_letter_submission_matches_regular_official(env):
    client = env["client"]
    approve(client, "שולחן")

    response = submit(client, TOKEN_A, "שולחנ")
    assert response.json() == {"status": "correct", "points": 2}


def test_reconcile_pending_regular_matches_final_official(env):
    client = env["client"]
    assert submit(client, TOKEN_A, "שולחנ").json() == {"status": "pending"}

    approve(client, "שולחן")

    assert progress(client, TOKEN_A) == {
        "solved": [CLUE_ID],
        "revealed": [],
        "answers": {CLUE_ID: "שולחנ"},
        "pending": [],
        "rejected": [],
    }


def test_pending_answer_survives_rejoin(env):
    client = env["client"]

    assert submit(client, TOKEN_A).json() == {"status": "pending"}

    client.cookies.clear()
    rejoined = client.post(
        f"/rooms/{ROOM_ID}/join", json={"displayName": PLAYER_A}
    )
    assert rejoined.status_code == 200, rejoined.text
    assert rejoined.json()["playerId"] == PLAYER_A

    as_player(client, rejoined.json()["sessionToken"])
    assert progress(client, rejoined.json()["sessionToken"]) == {
        "solved": [],
        "revealed": [],
        "answers": {CLUE_ID: ANSWER},
        "pending": [CLUE_ID],
        "rejected": [],
    }


def test_real_puzzle_seed_includes_hebrew_display_clues():
    from app.api.routes.e2e import _load_real_puzzle

    puzzle = _load_real_puzzle()

    assert puzzle.displayClues is not None
    assert len(puzzle.displayClues) == 24
    assert all(clue.text.strip() for clue in puzzle.displayClues)
    display_ids = {clue.clueId for clue in puzzle.displayClues}
    assert display_ids >= {"A1", "D1", "A21", "D18"}
    assert sum(clue.direction == "across" for clue in puzzle.displayClues) == 12
    assert sum(clue.direction == "down" for clue in puzzle.displayClues) == 12
    assert all(clue.text.strip() for clue in puzzle.clues)
