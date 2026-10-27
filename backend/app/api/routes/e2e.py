import json
import re
import secrets
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...adapters.parser_adapter import normalize_parser_response
from ...models.answers import OfficialAnswers
from ...models.puzzle import Clue, Puzzle
from ...models.room import Player, Room, RoomStatus
from ...services import firestore_publisher
from ...services import scoring_service
from ...services.puzzle_utils import validate_puzzle_structure
from . import admin_puzzles as admin_puzzles_module
from . import rooms as rooms_module
from . import submissions as submissions_module

router = APIRouter()

REAL_PUZZLE_PATH = (
    Path(__file__).resolve().parents[4]
    / "fixtures"
    / "parser-responses"
    / "real_puzzle.json"
)
REAL_CLUES_PATH = (
    Path(__file__).resolve().parents[4]
    / "fixtures"
    / "a_clues.json"
)


def _answer_length(text: str) -> int:
    groups = re.findall(r"\(([\d,\s]+)\)", text)
    if not groups:
        return 1
    return sum(
        int(part)
        for part in groups[-1].split(",")
        if part.strip().isdigit()
    ) or 1


def _load_real_display_clues() -> list[Clue]:
    with REAL_CLUES_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    clues: list[Clue] = []
    for entry in raw:
        number = entry["number"]
        direction = entry["direction"]
        prefix = "A" if direction == "across" else "D"
        clues.append(
            Clue(
                clueId=f"{prefix}{number}",
                number=number,
                direction=direction,
                text=entry["text"],
                answerLength=_answer_length(entry["text"]),
            )
        )
    return clues


def _load_real_puzzle() -> Puzzle:
    with REAL_PUZZLE_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    puzzle = normalize_parser_response(raw)
    display_clues = _load_real_display_clues()
    text_by_clue = {clue.clueId: clue.text for clue in display_clues}
    grid_ids = {clue.clueId for clue in puzzle.clues}
    unmatched_display = [
        clue for clue in display_clues if clue.clueId not in grid_ids
    ]
    merged_clues: list[Clue] = []
    for clue in puzzle.clues:
        if clue.clueId in text_by_clue:
            merged_clues.append(
                clue.model_copy(update={"text": text_by_clue[clue.clueId]})
            )
            continue
        match = next(
            (
                candidate
                for candidate in unmatched_display
                if candidate.direction == clue.direction
                and candidate.answerLength == clue.answerLength
            ),
            None,
        )
        if match is not None:
            unmatched_display.remove(match)
            merged_clues.append(clue.model_copy(update={"text": match.text}))
        else:
            merged_clues.append(clue)
    return puzzle.model_copy(
        update={"clues": merged_clues, "displayClues": display_clues}
    )


def _reset_room(room_id: str) -> None:
    rooms_module.room_repository._rooms.pop(room_id, None)
    rooms_module.player_repository._players = {
        k: v for k, v in rooms_module.player_repository._players.items() if k[0] != room_id
    }
    scoring_service._default_service._score_repository._events = {
        k: v
        for k, v in scoring_service._default_service._score_repository._events.items()
        if v.roomId != room_id
    }
    submissions_module.submission_repository._submissions = {
        k: v
        for k, v in submissions_module.submission_repository._submissions.items()
        if v.roomId != room_id
    }
    rooms_module._sessions = {
        k: v for k, v in rooms_module._sessions.items() if v[0] != room_id
    }
    from ...services import admin_solves

    admin_solves.remove_room(room_id)


class E2ESeedRequest(BaseModel):
    roomId: str
    title: str = "E2E Room"
    puzzle: Puzzle | None = None
    officialAnswers: OfficialAnswers | None = None
    status: RoomStatus = RoomStatus.active


@router.post("/e2e/seed", status_code=201)
def seed_room(body: E2ESeedRequest):
    answers_provided = body.officialAnswers is not None
    puzzle = body.puzzle
    official_answers = body.officialAnswers
    if puzzle is None:
        puzzle = _load_real_puzzle()
    if official_answers is None:
        official_answers = OfficialAnswers(puzzleId=puzzle.puzzleId, answers={})

    if official_answers.puzzleId != puzzle.puzzleId:
        raise HTTPException(
            status_code=400,
            detail="officialAnswers.puzzleId must match puzzle.puzzleId",
        )

    errors = validate_puzzle_structure(puzzle)
    if answers_provided:
        clue_ids = {clue.clueId for clue in puzzle.clues}
        missing = sorted(clue_ids - set(official_answers.answers.keys()))
        if missing:
            errors.append(f"Missing official answers for clues: {', '.join(missing)}")
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    puzzle_id = f"puzzle-{secrets.token_hex(8)}"
    saved_puzzle = puzzle.model_copy(update={"puzzleId": puzzle_id})
    saved_answers = official_answers.model_copy(update={"puzzleId": puzzle_id})
    admin_puzzles_module.puzzle_repository.save_snapshot(saved_puzzle)
    admin_puzzles_module.answer_repository.save(saved_answers)

    _reset_room(body.roomId)

    admin_id = f"admin-{secrets.token_hex(8)}"
    admin_player = Player(
        roomId=body.roomId,
        playerId=admin_id,
        displayName="E2E Admin",
        color="#FF0000",
        role="admin",
    )
    rooms_module.player_repository.add(admin_player)
    admin_token = secrets.token_hex(16)
    rooms_module._sessions[admin_token] = (body.roomId, admin_id)

    room = Room(
        roomId=body.roomId,
        title=body.title,
        status=body.status,
        puzzleSnapshot=saved_puzzle,
        creatorId=admin_id,
    )
    rooms_module.room_repository.create(room)
    firestore_publisher.publish_room(body.roomId)
    return {
        "roomId": room.roomId,
        "puzzleId": puzzle_id,
        "status": room.status.value,
        "adminSessionToken": admin_token,
    }


@router.post("/test/reset")
def reset_all_state():
    """Wipe all in-memory state for test isolation."""
    from ...repositories.in_memory import (
        InMemoryAdminSolveRepository,
        InMemoryPlayerIdentityRepository,
        InMemoryPlayerTotalRepository,
    )
    from ...services import admin_solves, player_totals
    from . import admin as admin_module
    from . import drafts as drafts_module

    rooms_module.room_repository._rooms.clear()
    rooms_module.player_repository._players.clear()
    rooms_module._sessions.clear()
    scoring_service._default_service._score_repository._events.clear()
    scoring_service._default_service._public_clue_states.clear()
    submissions_module.submission_repository._submissions.clear()
    drafts_module.player_clue_state_repository.states.clear()
    admin_puzzles_module.puzzle_repository._puzzles.clear()
    admin_module.answer_repository._answers.clear()
    admin_module._admin_password_tokens.clear()
    rooms_module.identity_repository = InMemoryPlayerIdentityRepository()
    player_totals.repository = InMemoryPlayerTotalRepository()
    admin_solves.repository = InMemoryAdminSolveRepository()
    return {"status": "ok"}
