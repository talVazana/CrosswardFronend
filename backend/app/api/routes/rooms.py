import secrets
import threading
from collections import Counter

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel, Field

from ...models.room import ASSIGNED_PLAYER_COLORS, Player, PlayerIdentity
from ...repositories.in_memory import (
    InMemoryPlayerIdentityRepository,
    InMemoryPlayerRepository,
    InMemoryRoomRepository,
)
from ...repositories.interfaces import (
    PlayerIdentityRepository,
    PlayerRepository,
    RoomRepository,
)
from ...services import firestore_publisher, scoring_service
from ...services.room_service import RoomService

router = APIRouter()

SESSION_COOKIE_NAME = "Session-Token"
# One cookie holds one token per room. Browsers cap a cookie near 4 KB, and each
# token is 33 characters with its separator, so 100 rooms fits with room to spare.
MAX_SESSION_TOKENS = 100

room_repository: RoomRepository = InMemoryRoomRepository()
player_repository: PlayerRepository = InMemoryPlayerRepository()
identity_repository: PlayerIdentityRepository = InMemoryPlayerIdentityRepository()
room_service = RoomService(room_repository, player_repository)

_sessions: dict[str, tuple[str, str]] = {}
_join_lock = threading.Lock()


def split_session_tokens(raw: str | None) -> list[str]:
    """Split the session cookie into its per-room tokens."""
    if not raw:
        return []
    return [token for token in raw.split("|") if token]


def get_room_session(raw: str | None, room_id: str) -> tuple[str, str] | None:
    """Return the (roomId, playerId) session for one room from a multi-room cookie."""
    for token in split_session_tokens(raw):
        session = _sessions.get(token)
        if session is not None and session[0] == room_id:
            return session
    return None


def _cookie_value(raw: str | None, room_id: str, token: str) -> str:
    tokens = [
        existing
        for existing in split_session_tokens(raw)
        if _sessions.get(existing) is not None and _sessions[existing][0] != room_id
    ]
    tokens.append(token)
    return "|".join(tokens[-MAX_SESSION_TOKENS:])


def _identity_key(display_name: str) -> str:
    return display_name.strip().casefold()


def _next_identity_color() -> str:
    counts = Counter(
        identity.color.upper() for identity in identity_repository.list_all()
    )
    return min(
        ASSIGNED_PLAYER_COLORS,
        key=lambda color: (
            counts.get(color.upper(), 0),
            ASSIGNED_PLAYER_COLORS.index(color),
        ),
    )


def _sync_room_identities(room_id: str) -> None:
    """Give every existing room player an identity so colors never change."""
    for player in player_repository.list_by_room(room_id):
        if player.role != "player":
            continue
        key = _identity_key(player.displayName)
        if identity_repository.get(key) is not None:
            continue
        identity = PlayerIdentity(displayName=player.displayName, color=player.color)
        identity_repository.save(key, identity)
        firestore_publisher.publish_player_identity(key, identity)


def _identity_for(display_name: str) -> PlayerIdentity:
    key = _identity_key(display_name)
    identity = identity_repository.get(key)
    if identity is None:
        identity = PlayerIdentity(
            displayName=display_name, color=_next_identity_color()
        )
        identity_repository.save(key, identity)
        firestore_publisher.publish_player_identity(key, identity)
    return identity


def _apply_identity_color(room_id: str, player: Player, color: str) -> bool:
    """Align one room player with the global identity color. True when changed."""
    if player.color.upper() == color.upper():
        return False
    old_color = player.color
    player.color = color
    others = [
        other
        for other in player_repository.list_by_room(room_id)
        if other.role == "player" and other.playerId != player.playerId
    ]
    if all(other.color.upper() != old_color.upper() for other in others):
        for (state_room, _clue_id), state in (
            scoring_service._default_service._public_clue_states.items()
        ):
            if state_room == room_id and (state.firstSolverColor or "").upper() == old_color.upper():
                state.firstSolverColor = color
    return True


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

    with _join_lock:
        _sync_room_identities(roomId)
        identity = _identity_for(desired_name)

        session = get_room_session(session_token, roomId)
        if session is not None:
            existing = player_repository.get(roomId, session[1])
            if (
                existing is not None
                and existing.displayName.casefold() == desired_name.casefold()
            ):
                if _apply_identity_color(roomId, existing, identity.color):
                    firestore_publisher.publish_room(roomId)
                return {"playerId": existing.playerId, "color": existing.color}

        reclaimed = next(
            (
                player
                for player in player_repository.list_by_room(roomId)
                if player.role == "player"
                and player.displayName.casefold() == desired_name.casefold()
            ),
            None,
        )

        changed = False
        if reclaimed is not None:
            player = reclaimed
            player_id = player.playerId
            changed = _apply_identity_color(roomId, player, identity.color)
        else:
            player_id = f"player-{secrets.token_hex(8)}"
            player = Player(
                roomId=roomId,
                playerId=player_id,
                displayName=desired_name,
                color=identity.color,
                role="player",
            )
            player_repository.add(player)

        token = secrets.token_hex(16)
        _sessions[token] = (roomId, player_id)
        firestore_publisher.publish_session(token, roomId, player_id)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=_cookie_value(session_token, roomId, token),
            httponly=True,
            secure=False,
            samesite="lax",
        )
    if changed or reclaimed is None:
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


@router.get("/rooms/{roomId}/me")
def get_room_player(
    roomId: str,
    session_token: str | None = Cookie(default=None, alias="Session-Token"),
):
    if session_token is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    session = get_room_session(session_token, roomId)
    if session is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    player = player_repository.get(roomId, session[1])
    if player is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "playerId": player.playerId,
        "displayName": player.displayName,
        "color": player.color,
    }


@router.get("/rooms/{roomId}/image")
def get_room_image(roomId: str):
    result = firestore_publisher.get_room_image(roomId)
    if result is None:
        raise HTTPException(status_code=404, detail="Image not found")
    data, content_type = result
    return Response(content=data, media_type=content_type)
