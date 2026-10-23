import json
import queue
import threading
import time
from queue import Empty

import pytest
from fastapi.testclient import TestClient

from app.api.routes import events as events_module
from app.api.routes import rooms as rooms_module
from app.main import app
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories.in_memory import InMemoryPlayerRepository, InMemoryRoomRepository
from app.services.event_broadcaster import EventBroadcaster

ROOM_ID = "room-1"
PLAYER_ID = "player-1"
ADMIN_ID = "admin-1"
TOKEN_PLAYER = "token-room-1-player-1"
TOKEN_ADMIN = "token-room-1-admin-1"
EVENTS_URL = f"/rooms/{ROOM_ID}/events"

PRIVATE_DRAFT = "SECRET-DRAFT-WORD"
OFFICIAL_ANSWER = "APPLE"


class FastEventBroadcaster(EventBroadcaster):
    def iter_events(self, queue):
        while True:
            try:
                event, data = queue.get(timeout=0.05)
            except Empty:
                yield ": keep-alive\n\n"
                continue
            yield f"event: {event}\ndata: {data}\n\n"


def make_puzzle() -> Puzzle:
    return Puzzle(
        puzzleId="puzzle-1",
        title="Task 038 Puzzle",
        width=1,
        height=1,
        cells=[
            Cell(
                row=0,
                col=0,
                type="white",
                number=1,
                startsAcross=True,
                startsDown=False,
            )
        ],
        clues=[
            Clue(
                clueId="A1",
                number=1,
                direction="across",
                text="Test clue",
                answerLength=5,
            )
        ],
    )


def make_room() -> Room:
    return Room(
        roomId=ROOM_ID,
        title="Task 038 Room",
        status=RoomStatus.active,
        puzzleSnapshot=make_puzzle(),
        creatorId=ADMIN_ID,
    )


def make_player(player_id: str, role: str, color: str) -> Player:
    return Player(
        roomId=ROOM_ID,
        playerId=player_id,
        displayName=player_id,
        color=color,
        role=role,
    )


@pytest.fixture
def env(monkeypatch):
    room_repository = InMemoryRoomRepository()
    room_repository.create(make_room())

    player_repository = InMemoryPlayerRepository()
    player_repository.add(make_player(PLAYER_ID, "player", "#AABBCC"))
    player_repository.add(make_player(ADMIN_ID, "admin", "#CCBBAA"))

    broadcaster = FastEventBroadcaster()

    monkeypatch.setattr(rooms_module, "room_repository", room_repository)
    monkeypatch.setattr(rooms_module, "player_repository", player_repository)
    monkeypatch.setattr(
        rooms_module,
        "_sessions",
        {TOKEN_PLAYER: (ROOM_ID, PLAYER_ID), TOKEN_ADMIN: (ROOM_ID, ADMIN_ID)},
    )
    monkeypatch.setattr(events_module, "broadcaster", broadcaster)

    with TestClient(app, base_url="https://testserver") as client:
        yield client, broadcaster


def wait_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def subscriber_count(broadcaster: EventBroadcaster) -> int:
    with broadcaster._lock:
        return len(broadcaster._subscribers.get(ROOM_ID, ()))


def wait_for_subscriber(broadcaster: EventBroadcaster) -> bool:
    return wait_until(lambda: subscriber_count(broadcaster) > 0)


class StreamReader:
    def __init__(self, response):
        self._response = response
        self._lines: queue.Queue = queue.Queue()
        self._current_event = None
        self._data_lines: list[str] = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        try:
            for line in self._response.iter_lines():
                self._lines.put(line)
        except Exception as exc:
            self._lines.put(exc)
        finally:
            self._lines.put(None)

    def read_event(self, event_name: str, timeout: float = 10.0):
        deadline = time.monotonic() + timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f"timed out waiting for event {event_name!r}")
            try:
                item = self._lines.get(timeout=remaining)
            except Empty:
                raise AssertionError(f"timed out waiting for event {event_name!r}")
            if item is None:
                raise AssertionError(f"stream ended before event {event_name!r}")
            if isinstance(item, Exception):
                raise AssertionError(
                    f"stream raised {item!r} before event {event_name!r}"
                )

            line = item
            if line.startswith("event:"):
                self._current_event = line.split(":", 1)[1].strip()
                self._data_lines = []
            elif line.startswith("data:"):
                self._data_lines.append(line.split(":", 1)[1].strip())
            elif line == "":
                if self._current_event == event_name and self._data_lines:
                    raw_data = "\n".join(self._data_lines)
                    return json.loads(raw_data), raw_data
                self._current_event = None
                self._data_lines = []


def assert_public_payload(raw_data: str, payload: dict) -> None:
    assert "draft" not in payload
    assert "officialAnswer" not in payload
    assert PRIVATE_DRAFT not in raw_data
    assert OFFICIAL_ANSWER not in raw_data


def test_valid_player_session_opens_sse_stream(env):
    client, broadcaster = env
    client.cookies.set("Session-Token", TOKEN_PLAYER)

    with client.stream("GET", EVENTS_URL) as response:
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/event-stream")
        assert wait_for_subscriber(broadcaster)


def test_valid_admin_session_opens_sse_stream(env):
    client, broadcaster = env
    client.cookies.set("Session-Token", TOKEN_ADMIN)

    with client.stream("GET", EVENTS_URL) as response:
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/event-stream")
        assert wait_for_subscriber(broadcaster)


def test_clue_solved_event_is_delivered_with_clue_id_and_first_solver_color(env):
    client, broadcaster = env
    client.cookies.set("Session-Token", TOKEN_PLAYER)
    first_solver_color = "#00FF00"

    with client.stream("GET", EVENTS_URL) as response:
        assert response.status_code == 200, response.text
        assert wait_for_subscriber(broadcaster)

        events_module.broadcast_clue_solved(ROOM_ID, "A1", first_solver_color, 2)
        reader = StreamReader(response)
        payload, _ = reader.read_event("CLUE_SOLVED")

    assert payload["clueId"] == "A1"
    assert payload["firstSolverColor"] == first_solver_color


def test_room_status_changed_event_is_delivered(env):
    client, broadcaster = env
    client.cookies.set("Session-Token", TOKEN_ADMIN)

    with client.stream("GET", EVENTS_URL) as response:
        assert response.status_code == 200, response.text
        assert wait_for_subscriber(broadcaster)

        events_module.broadcast_room_status_changed(ROOM_ID, "paused")
        reader = StreamReader(response)
        payload, _ = reader.read_event("ROOM_STATUS_CHANGED")

    assert payload == {"roomId": ROOM_ID, "status": "paused"}


def test_event_payloads_omit_draft_and_official_answer(env):
    client, broadcaster = env
    client.cookies.set("Session-Token", TOKEN_PLAYER)

    with client.stream("GET", EVENTS_URL) as response:
        assert response.status_code == 200, response.text
        assert wait_for_subscriber(broadcaster)

        reader = StreamReader(response)
        events_module.broadcast_room_status_changed(ROOM_ID, "paused")
        status_payload, status_raw = reader.read_event("ROOM_STATUS_CHANGED")
        assert_public_payload(status_raw, status_payload)

        events_module.broadcast_clue_solved(ROOM_ID, "A1", "#00FF00", 2)
        clue_payload, clue_raw = reader.read_event("CLUE_SOLVED")
        assert_public_payload(clue_raw, clue_payload)


@pytest.mark.parametrize("cookie", [None, "invalid-token"])
def test_connection_without_valid_session_cookie_is_rejected(env, cookie):
    client, broadcaster = env
    if cookie is not None:
        client.cookies.set("Session-Token", cookie)

    response = client.get(EVENTS_URL)

    assert response.status_code in (401, 403), response.text
    assert subscriber_count(broadcaster) == 0


def test_connection_for_missing_player_is_rejected(env):
    client, broadcaster = env
    rooms_module.player_repository._players.pop((ROOM_ID, PLAYER_ID))
    client.cookies.set("Session-Token", TOKEN_PLAYER)

    response = client.get(EVENTS_URL)

    assert response.status_code in (401, 403), response.text
    assert subscriber_count(broadcaster) == 0


def test_disconnecting_client_does_not_crash_broadcaster(env):
    client, broadcaster = env
    client.cookies.set("Session-Token", TOKEN_PLAYER)

    with client.stream("GET", EVENTS_URL) as response:
        assert response.status_code == 200, response.text
        assert wait_for_subscriber(broadcaster)
        reader = StreamReader(response)
        events_module.broadcast_clue_solved(ROOM_ID, "A1", "#00FF00", 2)
        reader.read_event("CLUE_SOLVED")

    events_module.broadcast_clue_solved(ROOM_ID, "A1", "#00FF00", 2)

    abandoned_queue = broadcaster.subscribe(ROOM_ID)
    broadcaster.unsubscribe(ROOM_ID, abandoned_queue)
    events_module.broadcast_clue_solved(ROOM_ID, "A1", "#00FF00", 2)

