import secrets
import threading

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...models.gameplay import Submission, SubmissionStatus, utc_now
from ...repositories.in_memory import InMemorySubmissionRepository
from ...repositories.interfaces import SubmissionRepository
from ...services import scoring_service
from ...services.puzzle_utils import normalize_answer
from . import admin as admin_module
from . import rooms as rooms_module

router = APIRouter()

submission_repository: SubmissionRepository = InMemorySubmissionRepository()
answer_repository = admin_module.answer_repository

_clue_locks: dict[tuple[str, str], threading.Lock] = {}
_clue_locks_guard = threading.Lock()


def _get_clue_lock(room_id: str, clue_id: str) -> threading.Lock:
    key = (room_id, clue_id)
    with _clue_locks_guard:
        lock = _clue_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _clue_locks[key] = lock
        return lock


class SubmissionRequest(BaseModel):
    answer: str


def _resolve_player(request: Request, room_id: str) -> str:
    session_token = request.cookies.get(rooms_module.SESSION_COOKIE_NAME)
    if session_token is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    session = rooms_module._sessions.get(session_token)
    if session is None or session[0] != room_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    _, player_id = session
    if rooms_module.player_repository.get(room_id, player_id) is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return player_id


@router.post("/rooms/{roomId}/clues/{clueId}/submissions")
def submit_answer(roomId: str, clueId: str, body: SubmissionRequest, request: Request):
    player_id = _resolve_player(request, roomId)

    room = rooms_module.room_repository.get(roomId)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    answers = answer_repository.get(room.puzzleSnapshot.puzzleId)
    official_answer = answers.answers.get(clueId) if answers else None

    if official_answer is None:
        status = SubmissionStatus.pending
    elif normalize_answer(body.answer) == official_answer:
        status = SubmissionStatus.correct
    else:
        status = SubmissionStatus.incorrect

    submission = Submission(
        submissionId=f"submission-{secrets.token_hex(8)}",
        roomId=roomId,
        playerId=player_id,
        clueId=clueId,
        answer=body.answer,
        serverTimestamp=utc_now(),
        status=status,
        pointsAwarded=0,
    )
    submission_repository.add(submission)

    if status != SubmissionStatus.correct:
        return {"status": status.value}

    player = rooms_module.player_repository.get(roomId, player_id)
    player_role = player.role if player else "player"
    player_color = player.color if player else ""

    lock = _get_clue_lock(roomId, clueId)
    with lock:
        points = scoring_service.calculate_points(
            roomId, clueId, player_id, True, player_role
        )
        if points > 0:
            scoring_service.apply_score(roomId, clueId, player_id, points, player_color)
        submission_repository.update_status(
            submission.submissionId, SubmissionStatus.correct, points
        )
    return {"status": "correct", "points": points}
