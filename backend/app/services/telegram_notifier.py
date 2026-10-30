"""Send room announcements to a Telegram group.

Notifications are best-effort and non-blocking, like the Firestore publisher.
When the bot token or chat id is missing, announcements are skipped and the
game continues normally.

Environment variables:
- ``TELEGRAM_BOT_TOKEN``: token from BotFather.
- ``TELEGRAM_CHAT_ID``: target group chat id (negative number for groups).
- ``PUBLIC_APP_URL``: optional frontend base URL used for join links.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def _bot_token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def _chat_id() -> str:
    return os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def _send_allowed() -> bool:
    """Keep the test suite offline even when tokens are present on the machine."""
    if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get(
        "TELEGRAM_ALLOW_IN_TESTS"
    ):
        return False
    return True


def is_enabled() -> bool:
    return _send_allowed() and bool(_bot_token() and _chat_id())


def _player_count(room_id: str) -> int:
    from ..api.routes import rooms as rooms_module

    return sum(
        1
        for player in rooms_module.player_repository.list_by_room(room_id)
        if player.role == "player"
    )


def _player_scores(room_id: str) -> dict[str, int]:
    from . import scoring_service

    totals: dict[str, int] = {}
    for event in scoring_service._default_service._score_repository.list_by_room(
        room_id
    ):
        totals[event.playerId] = totals.get(event.playerId, 0) + event.points
    return totals


def _winner_text(room_id: str) -> str:
    from ..api.routes import rooms as rooms_module

    players = [
        player
        for player in rooms_module.player_repository.list_by_room(room_id)
        if player.role == "player"
    ]
    if not players:
        return "No players"

    totals = _player_scores(room_id)
    best = max(totals.get(player.playerId, 0) for player in players)
    if best <= 0:
        return "No winner (no points)"

    winners = [
        player.displayName
        for player in players
        if totals.get(player.playerId, 0) == best
    ]
    if len(winners) == 1:
        return f"{winners[0]} ({best} pts)"
    return f"Tie: {', '.join(winners)} ({best} pts each)"


def _admin_vs_players(room_id: str) -> str:
    from . import statistics

    stats = statistics.build_statistics(room_id)
    return f"{stats['adminTotal']} - {stats['playersTotal']}"


def format_started_message(room) -> str:
    lines = [
        f"Game started: {room.title}",
        f"Room: {room.roomId}",
        f"Players: {_player_count(room.roomId)}",
    ]
    base_url = os.environ.get("PUBLIC_APP_URL", "").strip().rstrip("/")
    if base_url:
        lines.append(f"Join: {base_url}/rooms/{room.roomId}/join")
    return "\n".join(lines)


def format_finished_message(room) -> str:
    return "\n".join(
        [
            f"Game finished: {room.title}",
            f"Winner: {_winner_text(room.roomId)}",
            f"Admin vs players (clues): {_admin_vs_players(room.roomId)}",
            f"Room: {room.roomId}",
        ]
    )


def _send_message(text: str) -> bool:
    token = _bot_token()
    chat_id = _chat_id()
    if not token or not chat_id:
        return False

    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5):
            return True
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("Telegram notification failed: %s", exc)
        return False


def _send_async(text: str) -> None:
    if not is_enabled():
        return
    threading.Thread(target=_send_message, args=(text,), daemon=True).start()


def notify_game_started(room) -> None:
    if not is_enabled():
        return
    _send_async(format_started_message(room))


def notify_game_finished(room) -> None:
    if not is_enabled():
        return
    _send_async(format_finished_message(room))
