from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...models.answers import OfficialAnswers
from ...models.room import Room, RoomStatus
from ...repositories.in_memory import InMemoryAnswerRepository
from ...repositories.interfaces import AnswerRepository
from ...services.puzzle_utils import normalize_answer
from ...services.reconciliation_service import reconcile_pending_submissions
from . import rooms as rooms_module

router = APIRouter()

answer_repository: AnswerRepository = InMemoryAnswerRepository()

_ENDPOINT_TRANSITIONS: dict[str, tuple[frozenset[RoomStatus], RoomStatus]] = {
    "start": (frozenset({RoomStatus.lobby}), RoomStatus.active),
    "pause": (frozenset({RoomStatus.active}), RoomStatus.paused),
    "resume": (frozenset({RoomStatus.paused}), RoomStatus.active),
    "finish": (frozenset({RoomStatus.active, RoomStatus.paused}), RoomStatus.finished),
    "close": (frozenset({RoomStatus.finished}), RoomStatus.closed),
}


class AnswerRequest(BaseModel):
    answer: str


def _resolve_admin(request: Request):
    session_token = request.cookies.get(rooms_module.SESSION_COOKIE_NAME)
    if session_token is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    session = rooms_module._sessions.get(session_token)
    if session is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    _, player_id = session
    player = rooms_module.player_repository.get(session[0], player_id)
    if player is None or player.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return player


@router.put("/admin/puzzles/{puzzleId}/clues/{clueId}/answer")
def save_official_answer(puzzleId: str, clueId: str, body: AnswerRequest, request: Request):
    admin = _resolve_admin(request)
    answers = answer_repository.get(puzzleId)
    if answers is None:
        answers = OfficialAnswers(puzzleId=puzzleId, answers={})
    official_answer = normalize_answer(body.answer)
    answers.answers[clueId] = official_answer
    answer_repository.save(answers)

    rooms = rooms_module.room_repository._rooms.values()
    for room in rooms:
        if room.puzzleSnapshot.puzzleId == puzzleId:
            reconcile_pending_submissions(room.roomId, clueId, official_answer)

    return {"status": "ok"}


def _admin_transition(roomId: str, action: str, request: Request) -> Room:
    _resolve_admin(request)
    allowed_sources, target = _ENDPOINT_TRANSITIONS[action]
    room = rooms_module.room_repository.get(roomId)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status not in allowed_sources:
        raise HTTPException(status_code=400, detail=f"Invalid transition from {room.status.value} to {target.value}")
    room.status = target
    rooms_module.room_repository.update(room)
    return room


@router.post("/admin/rooms/{roomId}/start")
def start_room(roomId: str, request: Request):
    return _admin_transition(roomId, "start", request)


@router.post("/admin/rooms/{roomId}/pause")
def pause_room(roomId: str, request: Request):
    return _admin_transition(roomId, "pause", request)


@router.post("/admin/rooms/{roomId}/resume")
def resume_room(roomId: str, request: Request):
    return _admin_transition(roomId, "resume", request)


@router.post("/admin/rooms/{roomId}/finish")
def finish_room(roomId: str, request: Request):
    return _admin_transition(roomId, "finish", request)


@router.post("/admin/rooms/{roomId}/close")
def close_room(roomId: str, request: Request):
    return _admin_transition(roomId, "close", request)
