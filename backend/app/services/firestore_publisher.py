"""Mirror public room state into the local Firestore emulator.

The FastAPI backend remains the source of truth for game logic. This module
publishes a read-only snapshot of each room's public state (title, status,
players, puzzle, solved clues, scores) into Firestore so the frontend can read
it over `onSnapshot` instead of polling REST endpoints.

Implementation notes:

- Uses the Firestore REST API via the standard library, so the backend gains no
  new third-party dependency.
- Publishing is best-effort and non-blocking. If the emulator is down, the game
  keeps working; the write is retried on the next mutation.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

FIRESTORE_EMULATOR_HOST = os.environ.get("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
FIRESTORE_PROJECT_ID = os.environ.get("FIRESTORE_PROJECT_ID", "demo-crossword-arena")

_BASE_URL = (
    f"http://{FIRESTORE_EMULATOR_HOST}"
    f"/v1/projects/{FIRESTORE_PROJECT_ID}/databases/(default)/documents"
)


def _publishing_enabled() -> bool:
    """Disable Firestore publishing while the test suite runs."""
    return not os.environ.get("PYTEST_CURRENT_TEST")


def _firestore_value(value: object) -> dict:
    """Convert a plain Python value to a Firestore REST ``Value`` object."""
    if value is None:
        return {"nullValue": None}
    if value is True or value is False:
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, (bytes, bytearray)):
        return {"bytesValue": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_firestore_value(item) for item in value]}}
    if isinstance(value, dict):
        return {
            "mapValue": {
                "fields": {str(key): _firestore_value(item) for key, item in value.items()}
            }
        }
    raise TypeError(f"Unsupported Firestore value type: {type(value)!r}")


def _write_document(collection: str, document_id: str, data: dict) -> None:
    fields = {str(key): _firestore_value(value) for key, value in data.items()}
    body = json.dumps({"fields": fields}).encode("utf-8")

    field_paths = "&".join(
        f"updateMask.fieldPaths={key}" for key in fields.keys()
    )
    url = f"{_BASE_URL}/{collection}/{document_id}?{field_paths}"

    request = urllib.request.Request(
        url,
        data=body,
        method="PATCH",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer owner",
        },
    )
    try:
        urllib.request.urlopen(request, timeout=3)
    except (urllib.error.URLError, OSError, TimeoutError):
        # Emulator unavailable. Ignore; the next mutation will republish.
        pass


def build_room_payload(room_id: str) -> dict | None:
    """Assemble the public state snapshot for one room."""
    from ..api.routes import rooms as rooms_module
    from ..services import scoring_service

    room = rooms_module.room_repository.get(room_id)
    if room is None:
        return None

    players = [
        player
        for player in rooms_module.player_repository.list_by_room(room_id)
        if player.role == "player"
    ]

    totals: dict[str, int] = {}
    for event in scoring_service._default_service._score_repository.list_by_room(room_id):
        totals[event.playerId] = totals.get(event.playerId, 0) + event.points

    puzzle = room.puzzleSnapshot
    clue_count = len(puzzle.displayClues if puzzle.displayClues else puzzle.clues)

    return {
        "roomId": room.roomId,
        "id": room.roomId,
        "title": room.title,
        "status": room.status.value,
        "width": puzzle.width,
        "height": puzzle.height,
        "clueCount": clue_count,
        "playerCount": len(players),
        "puzzle": puzzle.model_dump(),
        "solvedClues": scoring_service._default_service.list_solved_clues(room_id),
        "scoreEvents": [
            {
                "scoreEventId": event.scoreEventId,
                "playerId": event.playerId,
                "clueId": event.clueId,
                "points": event.points,
                "reason": event.reason,
            }
            for event in scoring_service._default_service._score_repository.list_by_room(room_id)
        ],
        "players": [
            {"id": p.playerId, "displayName": p.displayName, "color": p.color}
            for p in players
        ],
        "scores": [
            {
                "playerId": p.playerId,
                "displayName": p.displayName,
                "color": p.color,
                "totalPoints": totals.get(p.playerId, 0),
            }
            for p in players
        ],
        "updatedAt": int(time.time() * 1000),
        "createdAt": int(room.createdAt.timestamp() * 1000),
        "statistics": _statistics_payload(room_id),
    }


def _statistics_payload(room_id: str) -> dict:
    from ..services import statistics

    return statistics.build_statistics(room_id)


def publish_room(room_id: str) -> None:
    """Publish one room's public state to Firestore, non-blocking."""
    if not _publishing_enabled():
        return
    payload = build_room_payload(room_id)
    if payload is None:
        return
    thread = threading.Thread(
        target=_write_document,
        args=("rooms", room_id, payload),
        daemon=True,
    )
    thread.start()


def publish_all_rooms() -> None:
    """Publish every room currently held in memory."""
    if not _publishing_enabled():
        return
    from ..api.routes import rooms as rooms_module

    for room_id in list(rooms_module.room_repository._rooms.keys()):
        publish_room(room_id)


def publish_room_image(
    room_id: str, image_bytes: bytes, content_type: str = "image/jpeg"
) -> None:
    """Store the source crossword image as a Firestore blob (best-effort)."""
    if not _publishing_enabled():
        return
    _write_document(
        "room_images",
        room_id,
        {"data": image_bytes, "contentType": content_type},
    )


def get_room_image(room_id: str) -> tuple[bytes, str] | None:
    """Read the source crossword image blob for a room."""
    url = f"{_BASE_URL}/room_images/{room_id}"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": "Bearer owner"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            document = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None

    fields = document.get("fields", {})
    data_field = fields.get("data", {}).get("bytesValue")
    content_type = fields.get("contentType", {}).get("stringValue", "image/jpeg")
    if not data_field:
        return None
    return base64.b64decode(data_field), content_type


def _delete_document(collection: str, document_id: str) -> None:
    url = f"{_BASE_URL}/{collection}/{document_id}"
    request = urllib.request.Request(
        url,
        method="DELETE",
        headers={"Authorization": "Bearer owner"},
    )
    try:
        urllib.request.urlopen(request, timeout=3)
    except (urllib.error.URLError, OSError):
        pass


def publish_player_identity(name_key: str, identity) -> None:
    """Persist one player's name and color so every room uses the same color."""
    if not _publishing_enabled():
        return
    _write_document(
        "player_identities",
        urllib.parse.quote(name_key, safe=""),
        {
            "nameKey": name_key,
            "displayName": identity.displayName,
            "color": identity.color,
            "createdAt": identity.createdAt.isoformat(),
        },
    )


def publish_player_total(name_key: str, total) -> None:
    """Persist one player's lifetime score across rooms."""
    if not _publishing_enabled():
        return
    _write_document(
        "player_totals",
        urllib.parse.quote(name_key, safe=""),
        {
            "nameKey": name_key,
            "displayName": total.displayName,
            "totalScore": total.totalScore,
            "updatedAt": total.updatedAt.isoformat(),
        },
    )


def publish_admin_solve(solve) -> None:
    """Persist one admin-first solve so statistics survive a restart."""
    if not _publishing_enabled():
        return
    _write_document(
        "admin_solves",
        urllib.parse.quote(f"{solve.roomId}__{solve.clueId}", safe=""),
        {
            "roomId": solve.roomId,
            "clueId": solve.clueId,
            "adminId": solve.adminId,
            "solvedAt": solve.solvedAt.isoformat(),
        },
    )


def delete_room_docs(room_id: str, puzzle_id: str | None = None) -> None:
    """Remove a room's Firestore snapshot and image blob (best-effort)."""
    _delete_document("rooms", room_id)
    _delete_document("room_images", room_id)
    if puzzle_id is not None:
        _delete_document("puzzle_answers", puzzle_id)
    for document in read_collection("submissions"):
        if document.get("roomId") == room_id:
            _delete_document("submissions", document["_id"])
    for document in read_collection("admin_solves"):
        if document.get("roomId") == room_id:
            _delete_document("admin_solves", document["_id"])


def publish_answers(puzzle_id: str, answers: dict[str, str]) -> None:
    """Persist the official answer key so restarts keep admin answers."""
    if not _publishing_enabled():
        return
    _write_document("puzzle_answers", puzzle_id, {"answers": dict(answers)})


def publish_session(token: str, room_id: str, player_id: str) -> None:
    """Persist a player session token so it survives a backend restart."""
    if not _publishing_enabled():
        return
    _write_document("sessions", token, {"roomId": room_id, "playerId": player_id})


def publish_submission(submission) -> None:
    """Persist a player submission so pending review and rejections survive a restart."""
    if not _publishing_enabled():
        return
    _write_document(
        "submissions",
        submission.submissionId,
        {
            "roomId": submission.roomId,
            "playerId": submission.playerId,
            "clueId": submission.clueId,
            "answer": submission.answer,
            "status": submission.status.value,
            "pointsAwarded": submission.pointsAwarded,
            "serverTimestamp": submission.serverTimestamp.isoformat(),
        },
    )


def delete_session(token: str) -> None:
    if not _publishing_enabled():
        return
    _delete_document("sessions", token)


def _player_state_doc_id(room_id: str, player_id: str, clue_id: str) -> str:
    return f"{room_id}__{player_id}__{clue_id}"


def publish_player_state(room_id: str, state) -> None:
    """Persist one player's private clue state (letters, revealed, scored)."""
    if not _publishing_enabled():
        return
    _write_document(
        "player_states",
        _player_state_doc_id(room_id, state.playerId, state.clueId),
        {
            "roomId": room_id,
            "playerId": state.playerId,
            "clueId": state.clueId,
            "draft": state.draft,
            "revealed": state.revealed,
            "scored": state.scored,
            "solution": state.solution,
        },
    )


def delete_player_state(room_id: str, player_id: str, clue_id: str) -> None:
    if not _publishing_enabled():
        return
    _delete_document(
        "player_states", _player_state_doc_id(room_id, player_id, clue_id)
    )


def publish_admin_token(token: str) -> None:
    """Persist an admin password session token across restarts."""
    if not _publishing_enabled():
        return
    _write_document("admin_sessions", token, {"token": token})


def _decode_value(value: dict) -> object:
    if "stringValue" in value:
        return value["stringValue"]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "nullValue" in value:
        return None
    if "timestampValue" in value:
        return value["timestampValue"]
    if "bytesValue" in value:
        return base64.b64decode(value["bytesValue"])
    if "arrayValue" in value:
        return [_decode_value(item) for item in value["arrayValue"].get("values", [])]
    if "mapValue" in value:
        return {
            key: _decode_value(item)
            for key, item in value["mapValue"].get("fields", {}).items()
        }
    return None


def decode_document(document: dict) -> dict:
    """Convert a Firestore REST document into plain Python values."""
    doc_id = str(document.get("name", "")).rsplit("/", 1)[-1]
    fields = {
        key: _decode_value(value)
        for key, value in document.get("fields", {}).items()
    }
    fields["_id"] = doc_id
    return fields


def read_collection(collection: str) -> list[dict]:
    """Read every document in a Firestore collection. Empty list on failure."""
    request = urllib.request.Request(
        f"{_BASE_URL}/{collection}",
        method="GET",
        headers={"Authorization": "Bearer owner"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            document = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return []
    return [decode_document(item) for item in document.get("documents", [])]
