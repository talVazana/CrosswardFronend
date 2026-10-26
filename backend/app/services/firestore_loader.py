"""Restore backend in-memory state from the Firestore mirror on startup.

The FastAPI backend keeps game state in memory. Without a restore step, every
restart wipes rooms, players, sessions, scores, and official answers. Firestore
already holds a public snapshot of each room, so this module rebuilds the
in-memory state from it.

Restored pieces:

- rooms and their puzzles
- players and their colors
- score totals and solved-clue markers
- official answer keys (``puzzle_answers`` collection)
- player session tokens (``sessions`` collection)
- admin password session tokens (``admin_sessions`` collection)

Best-effort only: if Firestore is unreachable, startup continues with an empty
state.
"""

from __future__ import annotations

from ..models.answers import OfficialAnswers
from ..models.gameplay import PublicClueState, ScoreEvent, utc_now
from ..models.room import Player, Room, RoomStatus
from ..models.puzzle import Puzzle
from . import firestore_publisher


def _restore_rooms() -> None:
    from ..api.routes import rooms as rooms_module
    from ..services import scoring_service

    service = scoring_service._default_service

    for document in firestore_publisher.read_collection("rooms"):
        room_id = document.get("roomId") or document.get("_id")
        puzzle_data = document.get("puzzle")
        if not room_id or not isinstance(puzzle_data, dict):
            continue
        if rooms_module.room_repository.get(room_id) is not None:
            continue

        try:
            puzzle = Puzzle(**puzzle_data)
            status = RoomStatus(document.get("status", RoomStatus.lobby.value))
        except Exception:
            continue

        room = Room(
            roomId=room_id,
            title=document.get("title") or "Restored room",
            status=status,
            puzzleSnapshot=puzzle,
            creatorId="restored",
        )
        rooms_module.room_repository.create(room)

        for entry in document.get("players") or []:
            player_id = entry.get("id") or entry.get("playerId")
            display_name = entry.get("displayName")
            color = entry.get("color")
            if not player_id or not display_name or not color:
                continue
            try:
                rooms_module.player_repository.add(
                    Player(
                        roomId=room_id,
                        playerId=player_id,
                        displayName=display_name,
                        color=color,
                        role="player",
                    )
                )
            except Exception:
                continue

        score_events = document.get("scoreEvents")
        if isinstance(score_events, list) and score_events:
            for event in score_events:
                player_id = event.get("playerId")
                clue_id = event.get("clueId")
                if not player_id or not clue_id:
                    continue
                service._score_repository.add_event(
                    ScoreEvent(
                        scoreEventId=event.get("scoreEventId")
                        or f"score-restored-{room_id}-{player_id}-{clue_id}",
                        roomId=room_id,
                        playerId=player_id,
                        clueId=clue_id,
                        points=int(event.get("points") or 0),
                        reason=event.get("reason") or "restored",
                        timestamp=utc_now(),
                    )
                )
        else:
            for entry in document.get("scores") or []:
                player_id = entry.get("playerId")
                points = int(entry.get("totalPoints") or 0)
                if not player_id or points <= 0:
                    continue
                service._score_repository.add_event(
                    ScoreEvent(
                        scoreEventId=f"score-restored-{room_id}-{player_id}",
                        roomId=room_id,
                        playerId=player_id,
                        clueId="__restored_total__",
                        points=points,
                        reason="restored_total",
                        timestamp=utc_now(),
                    )
                )

        for entry in document.get("solvedClues") or []:
            clue_id = entry.get("clueId")
            color = entry.get("firstSolverColor")
            if not clue_id or not color:
                continue
            service._public_clue_states[(room_id, clue_id)] = PublicClueState(
                clueId=clue_id,
                solved=True,
                firstSolverColor=color,
            )
            if not (isinstance(score_events, list) and score_events):
                service._score_repository.add_event(
                    ScoreEvent(
                        scoreEventId=f"score-restored-clue-{room_id}-{clue_id}",
                        roomId=room_id,
                        playerId="restored",
                        clueId=clue_id,
                        points=2,
                        reason="restored_clue",
                        timestamp=utc_now(),
                    )
                )


def _restore_answers() -> None:
    from ..api.routes import admin as admin_module

    for document in firestore_publisher.read_collection("puzzle_answers"):
        puzzle_id = document.get("_id")
        answers = document.get("answers")
        if not puzzle_id or not isinstance(answers, dict):
            continue
        admin_module.answer_repository.save(
            OfficialAnswers(puzzleId=puzzle_id, answers=dict(answers))
        )


def _restore_sessions() -> None:
    from ..api.routes import admin as admin_module
    from ..api.routes import rooms as rooms_module

    for document in firestore_publisher.read_collection("sessions"):
        token = document.get("_id")
        room_id = document.get("roomId")
        player_id = document.get("playerId")
        if not token or not room_id or not player_id:
            continue
        if rooms_module.player_repository.get(room_id, player_id) is None:
            continue
        rooms_module._sessions[token] = (room_id, player_id)

    for document in firestore_publisher.read_collection("admin_sessions"):
        token = document.get("_id") or document.get("token")
        if token:
            admin_module._admin_password_tokens.add(token)


def _restore_player_states() -> None:
    from ..api.routes import drafts as drafts_module
    from ..models.gameplay import PlayerClueState

    for document in firestore_publisher.read_collection("player_states"):
        room_id = document.get("roomId")
        player_id = document.get("playerId")
        clue_id = document.get("clueId")
        if not room_id or not player_id or not clue_id:
            continue
        drafts_module.player_clue_state_repository.save(
            PlayerClueState(
                playerId=player_id,
                clueId=clue_id,
                draft=document.get("draft") or "",
                revealed=bool(document.get("revealed")),
                scored=bool(document.get("scored")),
                solution=document.get("solution") or "",
            ),
            room_id,
        )


def restore_state() -> None:
    """Rebuild in-memory state from Firestore. Safe to call once at startup."""
    if not firestore_publisher._publishing_enabled():
        return
    try:
        _restore_rooms()
        _restore_answers()
        _restore_sessions()
        _restore_player_states()
    except Exception:
        # Never block startup because the mirror is unavailable.
        pass
