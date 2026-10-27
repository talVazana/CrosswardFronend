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
