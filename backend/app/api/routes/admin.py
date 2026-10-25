import secrets
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ...models.answers import OfficialAnswers
from ...models.room import Room, RoomStatus
from ...repositories.in_memory import InMemoryAnswerRepository
from ...repositories.interfaces import AnswerRepository
from ...services import scoring_service
from ...services.puzzle_utils import normalize_answer
from ...services.reconciliation_service import reconcile_pending_submissions
from . import events as events_module
from . import rooms as rooms_module

router = APIRouter()

ADMIN_SESSION_COOKIE_NAME = "Admin-Session-Token"
ADMIN_PASSWORD = "1234"

answer_repository: AnswerRepository = InMemoryAnswerRepository()
_admin_password_tokens: set[str] = set()

_ENDPOINT_TRANSITIONS: dict[str, tuple[frozenset[RoomStatus], RoomStatus]] = {
    "start": (frozenset({RoomStatus.lobby}), RoomStatus.active),
    "pause": (frozenset({RoomStatus.active}), RoomStatus.paused),
    "resume": (frozenset({RoomStatus.paused}), RoomStatus.active),
    "finish": (frozenset({RoomStatus.active, RoomStatus.paused}), RoomStatus.finished),
    "close": (frozenset({RoomStatus.finished}), RoomStatus.closed),
}


class AnswerRequest(BaseModel):
    answer: str


class AdminSessionRequest(BaseModel):
    token: str | None = None
    password: str | None = None


def _resolve_admin(request: Request):
    session_token = request.cookies.get(ADMIN_SESSION_COOKIE_NAME) or request.cookies.get(
        rooms_module.SESSION_COOKIE_NAME
    )
    if session_token is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if session_token in _admin_password_tokens:
        return SimpleNamespace(playerId="admin", displayName="Admin", role="admin")
    session = rooms_module._sessions.get(session_token)
    if session is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    _, player_id = session
    player = rooms_module.player_repository.get(session[0], player_id)
    if player is None or player.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return player


@router.post("/admin/session")
def create_admin_session(body: AdminSessionRequest, response: Response):
    if body.password is not None:
        if not secrets.compare_digest(body.password, ADMIN_PASSWORD):
            raise HTTPException(status_code=401, detail="Invalid admin password")
        token = secrets.token_hex(16)
        _admin_password_tokens.add(token)
        response.set_cookie(
            key=ADMIN_SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            secure=False,
            samesite="lax",
        )
        return {"roomId": None, "playerId": "admin", "displayName": "Admin"}

    if body.token is None:
        raise HTTPException(status_code=400, detail="Provide an admin password")

    session = rooms_module._sessions.get(body.token)
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid admin session token")
    room_id, player_id = session
    player = rooms_module.player_repository.get(room_id, player_id)
    if player is None or player.role != "admin":
        raise HTTPException(status_code=403, detail="This token is not an admin token")
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE_NAME,
        value=body.token,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return {
        "roomId": room_id,
        "playerId": player_id,
        "displayName": player.displayName,
    }


@router.get("/admin/rooms")
def list_admin_rooms(request: Request):
    _resolve_admin(request)
    return rooms_module.list_room_summaries()


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
    events_module.broadcast_room_status_changed(roomId, room.status.value)
    return room


@router.get("/admin/rooms/{roomId}")
def get_admin_room_state(roomId: str, request: Request):
    _resolve_admin(request)
    room = rooms_module.room_repository.get(roomId)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    from . import submissions as submissions_module

    players = [
        player
        for player in rooms_module.player_repository.list_by_room(roomId)
        if player.role == "player"
    ]
    totals: dict[str, int] = {}
    for event in scoring_service._default_service._score_repository.list_by_room(roomId):
        totals[event.playerId] = totals.get(event.playerId, 0) + event.points
    scores = [
        {
            "playerId": player.playerId,
            "displayName": player.displayName,
            "score": totals.get(player.playerId, 0),
        }
        for player in players
    ]
    answers = answer_repository.get(room.puzzleSnapshot.puzzleId)
    return {
        "roomId": room.roomId,
        "id": room.roomId,
        "title": room.title,
        "status": room.status.value,
        "puzzleId": room.puzzleSnapshot.puzzleId,
        "puzzle": room.puzzleSnapshot.model_dump(),
        "officialAnswers": answers.answers if answers else {},
        "solvedClues": scoring_service._default_service.list_solved_clues(roomId),
        "players": [
            {"id": p.playerId, "displayName": p.displayName, "color": p.color}
            for p in players
        ],
        "pendingSubmissions": [
            {
                "clueId": s.clueId,
                "playerId": s.playerId,
                "answer": s.answer,
            }
            for s in submissions_module.submission_repository.list_pending_by_room(roomId)
        ],
        "scores": scores,
    }


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
