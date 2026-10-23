from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ...models.gameplay import PlayerClueState
from ...models.room import RoomStatus
from ...repositories.in_memory import InMemoryPlayerClueStateRepository
from ...repositories.interfaces import PlayerClueStateRepository
from . import rooms as rooms_module

router = APIRouter()

player_clue_state_repository: PlayerClueStateRepository = InMemoryPlayerClueStateRepository()
_player_clue_states = player_clue_state_repository.states


class DraftRequest(BaseModel):
    draft: str = Field(max_length=100)


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


def _validate_request_identity(request: Request, room_id: str, player_id: str) -> None:
    cookie_token = request.cookies.get(rooms_module.SESSION_COOKIE_NAME)
    if cookie_token is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    session = rooms_module._sessions.get(cookie_token)
    if session is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    session_room_id, session_player_id = session
    if session_room_id != room_id or session_player_id != player_id:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.put("/rooms/{roomId}/clues/{clueId}/draft")
def save_draft(roomId: str, clueId: str, body: DraftRequest, request: Request):
    player_id = _resolve_player(request, roomId)
    _validate_request_identity(request, roomId, player_id)
    room = rooms_module.room_repository.get(roomId)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status not in (RoomStatus.active, RoomStatus.paused):
        raise HTTPException(status_code=400, detail="Drafts are currently disabled")
    state = player_clue_state_repository.get(roomId, player_id, clueId)
    if state is None:
        state = PlayerClueState(playerId=player_id, clueId=clueId)
    state.draft = body.draft
    player_clue_state_repository.save(state, roomId)
    return {"status": "ok"}


@router.get("/rooms/{roomId}/drafts")
def get_drafts(roomId: str, request: Request):
    player_id = _resolve_player(request, roomId)
    _validate_request_identity(request, roomId, player_id)
    return {
        state.clueId: state.draft
        for state in player_clue_state_repository.list_by_player(roomId, player_id)
    }
