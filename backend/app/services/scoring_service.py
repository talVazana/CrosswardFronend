import secrets
from typing import Optional

from ..models.gameplay import PublicClueState, ScoreEvent, utc_now
from ..repositories.in_memory import InMemoryScoreRepository
from ..repositories.interfaces import PlayerClueStateRepository, ScoreRepository


class ScoringService:
    def __init__(
        self,
        score_repository: ScoreRepository,
        player_clue_state_repository: Optional[PlayerClueStateRepository] = None,
    ):
        self._score_repository = score_repository
        self._player_clue_state_repository = player_clue_state_repository
        self._public_clue_states: dict[tuple[str, str], PublicClueState] = {}

    def _is_revealed(self, room_id: str, clue_id: str, player_id: str) -> bool:
        repo = self._player_clue_state_repository
        if repo is None:
            from ..api.routes import drafts as drafts_module

            repo = drafts_module.player_clue_state_repository
        state = repo.get(room_id, player_id, clue_id)
        return state is not None and state.revealed

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
        if self._is_revealed(room_id, clue_id, player_id):
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
        self._add_lifetime_points(room_id, player_id, points)

        key = (room_id, clue_id)
        state = self._public_clue_states.get(key)
        if state is None:
            state = PublicClueState(clueId=clue_id)
            self._public_clue_states[key] = state
        state.solved = True
        if points == 2:
            state.firstSolverColor = player_color

        return event

    def _add_lifetime_points(self, room_id: str, player_id: str, points: int) -> None:
        """Keep the player's cross-room total in sync with each awarded score."""
        if points <= 0:
            return
        from ..api.routes import rooms as rooms_module
        from . import player_totals

        player = rooms_module.player_repository.get(room_id, player_id)
        if player is None or player.role != "player":
            return
        player_totals.add_points(player.displayName, points)

    def get_public_clue_state(self, room_id: str, clue_id: str) -> PublicClueState:
        key = (room_id, clue_id)
        state = self._public_clue_states.get(key)
        if state is None:
            state = PublicClueState(clueId=clue_id)
            self._public_clue_states[key] = state
        return state

    def list_solved_clues(self, room_id: str) -> list[dict]:
        result = []
        for (rid, clue_id), state in self._public_clue_states.items():
            if rid == room_id and state.solved and state.firstSolverColor:
                result.append(
                    {"clueId": clue_id, "firstSolverColor": state.firstSolverColor}
                )
        return result


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
