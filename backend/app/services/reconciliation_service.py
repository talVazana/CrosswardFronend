from ..models.gameplay import SubmissionStatus
from ..services import firestore_publisher, scoring_service
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

    awarded_points = 0
    lock = _get_clue_lock(room_id, clue_id)
    with lock:
        for submission in pending:
            player = player_repository.get(room_id, submission.playerId)
            player_role = player.role if player else "player"
            player_color = player.color if player else ""

            if normalize_answer(submission.answer) == official_answer:
                drafts_module.mark_clue_scored(
                    room_id,
                    submission.playerId,
                    clue_id,
                    normalize_answer(submission.answer),
                )
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
                    awarded_points = max(awarded_points, points)
                submission_repository.update_status(
                    submission.submissionId, SubmissionStatus.correct, points
                )
                firestore_publisher.publish_submission(submission)
            else:
                submission_repository.update_status(
                    submission.submissionId, SubmissionStatus.incorrect, 0
                )
                firestore_publisher.publish_submission(submission)

    if awarded_points > 0:
        from ..api.routes import events as events_module

        public_state = scoring_service._default_service.get_public_clue_state(
            room_id, clue_id
        )
        events_module.broadcast_clue_solved(
            room_id, clue_id, public_state.firstSolverColor or "", awarded_points
        )
