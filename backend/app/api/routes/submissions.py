import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...models.gameplay import Submission, SubmissionStatus, utc_now
from ...repositories.in_memory import InMemorySubmissionRepository
from ...repositories.interfaces import SubmissionRepository
from ...services.puzzle_utils import normalize_answer
from . import admin as admin_module
from . import rooms as rooms_module

router = APIRouter()

submission_repository: SubmissionRepository = InMemorySubmissionRepository()
answer_repository = admin_module.answer_repository


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
    return {"status": status.value}
