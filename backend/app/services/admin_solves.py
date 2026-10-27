"""Track clues the admin solved first (statistics only, no scoring change)."""

from ..models.admin_solve import AdminSolve
from ..repositories.in_memory import InMemoryAdminSolveRepository

repository = InMemoryAdminSolveRepository()


def record_first_solve(room_id: str, clue_id: str, admin_id: str) -> bool:
    """Credit the admin only when no player solved the clue first.

    Returns True when a new admin solve was recorded, False otherwise.
    """
    from ..services import firestore_publisher, scoring_service

    events = scoring_service._default_service._score_repository.list_by_room(room_id)
    if any(event.clueId == clue_id and event.points == 2 for event in events):
        return False

    solve = AdminSolve(roomId=room_id, clueId=clue_id, adminId=admin_id)
    if not repository.add(solve):
        return False
    firestore_publisher.publish_admin_solve(solve)
    return True


def list_by_room(room_id: str) -> list[AdminSolve]:
    return repository.list_by_room(room_id)


def remove_room(room_id: str) -> None:
    repository.remove_room(room_id)
