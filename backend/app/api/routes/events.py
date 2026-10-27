import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ...services.event_broadcaster import broadcaster
from . import rooms as rooms_module

router = APIRouter()


def _resolve_member(request: Request, room_id: str):
    if rooms_module.room_repository.get(room_id) is None:
        raise HTTPException(status_code=404, detail="Room not found")
    session_token = request.cookies.get(rooms_module.SESSION_COOKIE_NAME)
    if session_token is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    session = rooms_module.get_room_session(session_token, room_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    _, player_id = session
    player = rooms_module.player_repository.get(room_id, player_id)
    if player is None or player.role not in ("player", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return player


@router.get("/rooms/{roomId}/events")
def stream_room_events(roomId: str, request: Request):
    player = _resolve_member(request, roomId)

    queue = broadcaster.subscribe(roomId)

    def event_stream():
        try:
            for chunk in broadcaster.iter_events(queue):
                yield chunk
        finally:
            broadcaster.unsubscribe(roomId, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def broadcast_room_status_changed(room_id: str, status: str) -> None:
    broadcaster.publish(
        room_id,
        "ROOM_STATUS_CHANGED",
        json.dumps({"roomId": room_id, "status": status}),
    )


def broadcast_clue_solved(
    room_id: str, clue_id: str, first_solver_color: str, points: int
) -> None:
    broadcaster.publish(
        room_id,
        "CLUE_SOLVED",
        json.dumps(
            {
                "roomId": room_id,
                "clueId": clue_id,
                "firstSolverColor": first_solver_color,
                "points": points,
            }
        ),
    )
