from ..models.gameplay import SubmissionStatus
from ..services import scoring_service
from ..services.puzzle_utils import normalize_answer


def reconcile_pending_submissions(room_id: str, clue_id: str, official_answer: str) -> None:
    from ..api.routes.rooms import player_repository
    from ..api.routes.submissions import _get_clue_lock, submission_repository

    from ..api.routes import drafts as drafts_module

    pending = [
        s
        for s in submission_repository.list_pending_by_room(room_id)
        if s.clueId == clue_id
    ]
    pending.sort(key=lambda s: s.serverTimestamp)

    lock = _get_clue_lock(room_id, clue_id)
    with lock:
        for submission in pending:
            player = player_repository.get(room_id, submission.playerId)
            player_role = player.role if player else "player"
            player_color = player.color if player else ""

            if normalize_answer(submission.answer) == official_answer:
                state = drafts_module.player_clue_state_repository.get(
                    room_id, submission.playerId, clue_id
                )
                revealed = state is not None and state.revealed
                points = (
                    0
                    if revealed
                    else scoring_service.calculate_points(
                        room_id, clue_id, submission.playerId, True, player_role
                    )
                )
                if points > 0:
                    scoring_service.apply_score(
                        room_id, clue_id, submission.playerId, points, player_color
                    )
                submission_repository.update_status(
                    submission.submissionId, SubmissionStatus.correct, points
                )
            else:
                submission_repository.update_status(
                    submission.submissionId, SubmissionStatus.incorrect, 0
                )
