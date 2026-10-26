import secrets
import threading

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel, Field

from ...models.room import ASSIGNED_PLAYER_COLORS, Player
from ...repositories.in_memory import InMemoryPlayerRepository, InMemoryRoomRepository
from ...repositories.interfaces import PlayerRepository, RoomRepository
from ...services import firestore_publisher
from ...services.room_service import RoomService

router = APIRouter()

SESSION_COOKIE_NAME = "Session-Token"

room_repository: RoomRepository = InMemoryRoomRepository()
player_repository: PlayerRepository = InMemoryPlayerRepository()
room_service = RoomService(room_repository, player_repository)

_sessions: dict[str, tuple[str, str]] = {}
_join_lock = threading.Lock()


def _assign_player_color(room_id: str) -> str:
    used = {
        player.color.upper()
        for player in player_repository.list_by_room(room_id)
        if player.role == "player"
    }
    for color in ASSIGNED_PLAYER_COLORS:
        if color.upper() not in used:
            return color
    players = [
        player
        for player in player_repository.list_by_room(room_id)
        if player.role == "player"
    ]
    return ASSIGNED_PLAYER_COLORS[len(players) % len(ASSIGNED_PLAYER_COLORS)]


def _service() -> RoomService:
    return RoomService(room_repository, player_repository)


def list_room_summaries() -> list[dict]:
    return _service().list_room_summaries()


class JoinRequest(BaseModel):
    displayName: str = Field(min_length=2, max_length=20)


@router.post("/rooms/{roomId}/join")
def join_room(roomId: str, body: JoinRequest, response: Response, session_token: str | None = Cookie(default=None, alias="Session-Token")):
    if room_repository.get(roomId) is None:
        raise HTTPException(status_code=404, detail="Room not found")

    desired_name = body.displayName.strip()

    if session_token is not None:
        session = _sessions.get(session_token)
        if session is not None and session[0] == roomId:
            existing = player_repository.get(roomId, session[1])
            if (
                existing is not None
                and existing.displayName.casefold() == desired_name.casefold()
            ):
                return {"playerId": existing.playerId, "color": existing.color}

    with _join_lock:
        active_player_ids = {
            player_id
            for token, (session_room_id, player_id) in _sessions.items()
            if session_room_id == roomId
        }
        reclaimed = next(
            (
                player
                for player in player_repository.list_by_room(roomId)
                if player.role == "player"
                and player.displayName.casefold() == desired_name.casefold()
                and player.playerId not in active_player_ids
            ),
            None,
        )

        if reclaimed is not None:
            player = reclaimed
            player_id = player.playerId
        else:
            player_id = f"player-{secrets.token_hex(8)}"
            player = Player(
                roomId=roomId,
                playerId=player_id,
                displayName=desired_name,
                color=_assign_player_color(roomId),
                role="player",
            )
            player_repository.add(player)

        token = secrets.token_hex(16)
        _sessions[token] = (roomId, player_id)
        firestore_publisher.publish_session(token, roomId, player_id)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            secure=False,
            samesite="lax",
        )
    firestore_publisher.publish_room(roomId)
    return {"playerId": player.playerId, "color": player.color}


@router.get("/rooms")
def list_rooms():
    return list_room_summaries()


@router.get("/rooms/{roomId}/state")
def get_room_state(roomId: str):
    try:
        state = _service().get_room_public_state(roomId)
    except ValueError:
        raise HTTPException(status_code=404, detail="Room not found")
    for player in state.get("players", []):
        player["playerId"] = player["id"]
    return state


@router.get("/rooms/{roomId}/image")
def get_room_image(roomId: str):
    result = firestore_publisher.get_room_image(roomId)
    if result is None:
        raise HTTPException(status_code=404, detail="Image not found")
    data, content_type = result
    return Response(content=data, media_type=content_type)
