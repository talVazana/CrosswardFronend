"""Restore backend in-memory state from the Firestore mirror on startup.

The FastAPI backend keeps game state in memory. Without a restore step, every
restart wipes rooms, players, sessions, scores, and official answers. Firestore
already holds a public snapshot of each room, so this module rebuilds the
in-memory state from it.

Restored pieces:

- rooms and their puzzles
- players and their colors
- score totals and solved-clue markers
- lifetime player totals across rooms (``player_totals`` collection)
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


def _restored_timestamp(value) -> "datetime":
    """Read a stored timestamp in epoch milliseconds or ISO form."""
    from datetime import datetime, timezone

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return utc_now()


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

        createdAt = _restored_timestamp(
            document.get("createdAt") or document.get("updatedAt")
        )
        room = Room(
            roomId=room_id,
            title=document.get("title") or "Restored room",
            status=status,
            puzzleSnapshot=puzzle,
            creatorId="restored",
            createdAt=createdAt,
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


def _restore_identities() -> None:
    from datetime import datetime

    from ..api.routes import rooms as rooms_module
    from ..models.room import PlayerIdentity

    for document in firestore_publisher.read_collection("player_identities"):
        name_key = document.get("nameKey")
        display_name = document.get("displayName")
        color = document.get("color")
        if not name_key or not display_name or not color:
            continue
        try:
            created = datetime.fromisoformat(document.get("createdAt") or "")
        except (ValueError, TypeError):
            continue
        rooms_module.identity_repository.save(
            name_key,
            PlayerIdentity(displayName=display_name, color=color, createdAt=created),
        )


def _restore_submissions() -> None:
    from datetime import datetime

    from ..api.routes import submissions as submissions_module
    from ..models.gameplay import Submission, SubmissionStatus

    for document in firestore_publisher.read_collection("submissions"):
        submission_id = document.get("_id")
        room_id = document.get("roomId")
        player_id = document.get("playerId")
        clue_id = document.get("clueId")
        if not submission_id or not room_id or not player_id or not clue_id:
            continue
        try:
            status = SubmissionStatus(document.get("status") or "pending")
            timestamp = datetime.fromisoformat(document.get("serverTimestamp") or "")
        except (ValueError, TypeError):
            continue
        submissions_module.submission_repository.add(
            Submission(
                submissionId=submission_id,
                roomId=room_id,
                playerId=player_id,
                clueId=clue_id,
                answer=document.get("answer") or "",
                serverTimestamp=timestamp,
                status=status,
                pointsAwarded=int(document.get("pointsAwarded") or 0),
            )
        )


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


def _restore_player_totals() -> None:
    from datetime import datetime

    from ..models.player_total import PlayerTotal
    from ..services import player_totals

    for document in firestore_publisher.read_collection("player_totals"):
        name_key = document.get("nameKey")
        display_name = document.get("displayName")
        if not name_key or not display_name:
            continue
        try:
            updated = datetime.fromisoformat(document.get("updatedAt") or "")
        except (ValueError, TypeError):
            continue
        player_totals.repository.save(
            name_key,
            PlayerTotal(
                displayName=display_name,
                totalScore=int(document.get("totalScore") or 0),
                updatedAt=updated,
            ),
        )


def _seed_player_totals() -> None:
    """Derive lifetime totals from stored score events when none were saved yet."""
    from ..api.routes import rooms as rooms_module
    from ..services import player_totals, scoring_service

    earned: dict[str, tuple[str, int]] = {}
    for room in rooms_module.room_repository.list_all():
        events = scoring_service._default_service._score_repository.list_by_room(
            room.roomId
        )
        by_player: dict[str, int] = {}
        for event in events:
            if event.playerId == "restored":
                continue
            by_player[event.playerId] = by_player.get(event.playerId, 0) + event.points
        for player in rooms_module.player_repository.list_by_room(room.roomId):
            if player.role != "player":
                continue
            points = by_player.get(player.playerId, 0)
            if points <= 0:
                continue
            key = player_totals.name_key(player.displayName)
            name, current = earned.get(key, (player.displayName, 0))
            earned[key] = (name, current + points)

    for key, (display_name, points) in earned.items():
        if player_totals.repository.get(key) is not None:
            continue
        player_totals.add_points(display_name, points)


def _restore_admin_solves() -> None:
    from datetime import datetime

    from ..models.admin_solve import AdminSolve
    from ..services import admin_solves

    for document in firestore_publisher.read_collection("admin_solves"):
        room_id = document.get("roomId")
        clue_id = document.get("clueId")
        admin_id = document.get("adminId")
        if not room_id or not clue_id or not admin_id:
            continue
        try:
            solved_at = datetime.fromisoformat(document.get("solvedAt") or "")
        except (ValueError, TypeError):
            solved_at = utc_now()
        admin_solves.repository.add(
            AdminSolve(
                roomId=room_id,
                clueId=clue_id,
                adminId=admin_id,
                solvedAt=solved_at,
            )
        )


def restore_state() -> None:
    """Rebuild in-memory state from Firestore. Safe to call once at startup."""
    if not firestore_publisher._publishing_enabled():
        return
    try:
        _restore_rooms()
        _restore_identities()
        _restore_player_totals()
        _seed_player_totals()
        _restore_answers()
        _restore_sessions()
        _restore_submissions()
        _restore_player_states()
        _restore_admin_solves()
        firestore_publisher.publish_all_rooms()
    except Exception:
        # Never block startup because the mirror is unavailable.
        pass
