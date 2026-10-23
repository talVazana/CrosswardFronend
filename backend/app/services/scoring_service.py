import secrets

from ..models.gameplay import PublicClueState, ScoreEvent, utc_now
from ..repositories.in_memory import InMemoryScoreRepository
from ..repositories.interfaces import ScoreRepository


class ScoringService:
    def __init__(self, score_repository: ScoreRepository):
        self._score_repository = score_repository
        self._public_clue_states: dict[tuple[str, str], PublicClueState] = {}

    def calculate_points(
        self,
        room_id: str,
        clue_id: str,
        player_id: str,
        is_correct: bool,
        player_role: str,
    ) -> int:
        if not is_correct:
            return 0
        if player_role == "admin":
            return 0
        events = self._score_repository.list_by_room(room_id)
        for event in events:
            if event.clueId == clue_id and event.playerId == player_id and event.points > 0:
                return 0
        for event in events:
            if event.clueId == clue_id and event.points > 0:
                return 1
        return 2

    def apply_score(
        self,
        room_id: str,
        clue_id: str,
        player_id: str,
        points: int,
        player_color: str,
    ) -> ScoreEvent:
        event = ScoreEvent(
            scoreEventId=f"score-{secrets.token_hex(8)}",
            roomId=room_id,
            playerId=player_id,
            clueId=clue_id,
            points=points,
            reason="correct_submission",
            timestamp=utc_now(),
        )
        self._score_repository.add_event(event)

        key = (room_id, clue_id)
        state = self._public_clue_states.get(key)
        if state is None:
            state = PublicClueState(clueId=clue_id)
            self._public_clue_states[key] = state
        state.solved = True
        if points == 2:
            state.firstSolverColor = player_color

        return event

    def get_public_clue_state(self, room_id: str, clue_id: str) -> PublicClueState:
        key = (room_id, clue_id)
        state = self._public_clue_states.get(key)
        if state is None:
            state = PublicClueState(clueId=clue_id)
            self._public_clue_states[key] = state
        return state


_default_service = ScoringService(InMemoryScoreRepository())


def calculate_points(
    room_id: str,
    clue_id: str,
    player_id: str,
    is_correct: bool,
    player_role: str,
) -> int:
    return _default_service.calculate_points(room_id, clue_id, player_id, is_correct, player_role)


def apply_score(
    room_id: str,
    clue_id: str,
    player_id: str,
    points: int,
    player_color: str,
) -> ScoreEvent:
    return _default_service.apply_score(room_id, clue_id, player_id, points, player_color)
