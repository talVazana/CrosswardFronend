"""Lifetime player scores across every room.

A player is identified by display name, the same key that assigns colors. The
total is kept after a room finishes or is deleted, so it survives both room
cleanup and backend restarts.
"""

from ..models.player_total import PlayerTotal
from ..repositories.in_memory import InMemoryPlayerTotalRepository

repository = InMemoryPlayerTotalRepository()


def name_key(display_name: str) -> str:
    return display_name.strip().casefold()


def get_total(display_name: str) -> int:
    total = repository.get(name_key(display_name))
    return total.totalScore if total is not None else 0


def add_points(display_name: str, points: int) -> PlayerTotal | None:
    """Add earned points to one player's lifetime total and mirror it."""
    if points <= 0:
        return None
    from . import firestore_publisher

    key = name_key(display_name)
    existing = repository.get(key)
    total = PlayerTotal(
        displayName=display_name,
        totalScore=(existing.totalScore if existing is not None else 0) + points,
    )
    repository.save(key, total)
    firestore_publisher.publish_player_total(key, total)
    return total


def rebuild() -> None:
    """Recompute every lifetime total from the current room score events.

    Called after a room is deleted so its points no longer count toward the
    lifetime leaderboard. Overwrites the in-memory totals and the Firestore
    mirror, and removes any player whose total drops to zero.
    """
    from ..api.routes import rooms as rooms_module
    from ..services import scoring_service
    from . import firestore_publisher

    earned: dict[str, tuple[str, int]] = {}
    for room in rooms_module.room_repository.list_all():
        by_player: dict[str, int] = {}
        for event in scoring_service._default_service._score_repository.list_by_room(
            room.roomId
        ):
            if event.playerId == "restored":
                continue
            by_player[event.playerId] = by_player.get(event.playerId, 0) + event.points
        for player in rooms_module.player_repository.list_by_room(room.roomId):
            if player.role != "player":
                continue
            points = by_player.get(player.playerId, 0)
            if points <= 0:
                continue
            key = name_key(player.displayName)
            display_name, current = earned.get(key, (player.displayName, 0))
            earned[key] = (display_name, current + points)

    for existing in list(repository.list_all()):
        key = name_key(existing.displayName)
        if key not in earned:
            repository.delete(key)
            firestore_publisher.delete_player_total(key)

    for key, (display_name, points) in earned.items():
        existing = repository.get(key)
        if existing is not None and existing.totalScore == points:
            continue
        total = PlayerTotal(displayName=display_name, totalScore=points)
        repository.save(key, total)
        firestore_publisher.publish_player_total(key, total)


def leaderboard() -> list[dict]:
    from ..api.routes import rooms as rooms_module

    totals = sorted(
        repository.list_all(), key=lambda total: (-total.totalScore, total.displayName)
    )
    entries = []
    for total in totals:
        identity = rooms_module.identity_repository.get(name_key(total.displayName))
        entries.append(
            {
                "displayName": total.displayName,
                "totalScore": total.totalScore,
                "color": identity.color if identity is not None else None,
            }
        )
    return entries
