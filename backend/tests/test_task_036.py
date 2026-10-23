import pytest
from fastapi.testclient import TestClient

from app.api.routes import admin_puzzles as admin_puzzles_module
from app.api.routes import rooms as rooms_module
from app.main import app
from app.models.room import Player
from app.repositories.in_memory import InMemoryPlayerRepository

ROOM_ID = "room-1"
ADMIN_ID = "admin-1"
PLAYER_ID = "player-1"
TOKEN_ADMIN = "token-admin"
TOKEN_PLAYER = "token-player"

PARSE_URL = "/admin/puzzles/parse"
SAVE_URL = "/admin/puzzles"


def make_player(player_id: str, role: str) -> Player:
    return Player(
        roomId=ROOM_ID,
        playerId=player_id,
        displayName=player_id,
        color="#AABBCC",
        role=role,
    )


def make_puzzle_dict(puzzle_id: str = "puz1") -> dict:
    cells = [
        {
            "row": row,
            "col": col,
            "type": "white",
            "number": 1 if (row, col) == (0, 2) else None,
            "startsAcross": (row, col) == (0, 2),
            "startsDown": False,
        }
        for row in range(3)
        for col in range(3)
    ]
    return {
        "puzzleId": puzzle_id,
        "title": "Task 036 Puzzle",
        "width": 3,
        "height": 3,
        "cells": cells,
        "clues": [
            {
                "clueId": "A1",
                "number": 1,
                "direction": "across",
                "text": "Clue A1",
                "answerLength": 3,
            }
        ],
    }


def make_payload(puzzle_id: str = "puz1") -> dict:
    return {
        "puzzle": make_puzzle_dict(puzzle_id),
        "officialAnswers": {
            "puzzleId": puzzle_id,
            "answers": {"A1": "CAT"},
        },
    }


@pytest.fixture
def clients(monkeypatch):
    player_repository = InMemoryPlayerRepository()
    player_repository.add(make_player(ADMIN_ID, "admin"))
    player_repository.add(make_player(PLAYER_ID, "player"))

    monkeypatch.setattr(rooms_module, "player_repository", player_repository)
    monkeypatch.setattr(
        rooms_module,
        "_sessions",
        {TOKEN_ADMIN: (ROOM_ID, ADMIN_ID), TOKEN_PLAYER: (ROOM_ID, PLAYER_ID)},
    )

    puzzle_repository = admin_puzzles_module.InMemoryPuzzleRepository()
    answer_repository = admin_puzzles_module.InMemoryAnswerRepository()
    monkeypatch.setattr(admin_puzzles_module, "puzzle_repository", puzzle_repository)
    monkeypatch.setattr(admin_puzzles_module, "answer_repository", answer_repository)

    with TestClient(app, base_url="https://testserver") as admin_client, TestClient(
        app, base_url="https://testserver"
    ) as player_client:
        admin_client.cookies.set("Session-Token", TOKEN_ADMIN)
        player_client.cookies.set("Session-Token", TOKEN_PLAYER)
        yield admin_client, player_client, puzzle_repository, answer_repository


def test_admin_fixture_parse_returns_200_puzzle_and_no_validation_errors(clients):
    admin_client, _, _, _ = clients
    response = admin_client.post(PARSE_URL, json={"use_fixture": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "puzzle" in body
    assert isinstance(body["puzzle"], dict)
    assert body["puzzle"]["width"] > 0 and body["puzzle"]["height"] > 0
    assert body["validation_errors"] == []


def test_admin_save_valid_puzzle_returns_201_and_persists(clients):
    admin_client, _, puzzle_repository, answer_repository = clients
    response = admin_client.post(SAVE_URL, json=make_payload())
    assert response.status_code == 201, response.text
    puzzle_id = response.json()["puzzleId"]
    assert isinstance(puzzle_id, str) and puzzle_id
    assert puzzle_id != "puz1"

    saved_puzzle = puzzle_repository.get_snapshot(puzzle_id)
    assert saved_puzzle is not None
    assert saved_puzzle.puzzleId == puzzle_id

    saved_answers = answer_repository.get(puzzle_id)
    assert saved_answers is not None
    assert saved_answers.answers == {"A1": "CAT"}


def test_admin_save_missing_official_answer_returns_400(clients):
    admin_client, _, puzzle_repository, answer_repository = clients
    payload = make_payload()
    payload["officialAnswers"]["answers"] = {}
    response = admin_client.post(SAVE_URL, json=payload)
    assert response.status_code == 400, response.text
    assert "missing" in response.text.lower()
    assert puzzle_repository.get_snapshot("puz1") is None
    assert answer_repository.get("puz1") is None


def test_admin_save_structurally_invalid_puzzle_returns_400(clients):
    admin_client, _, puzzle_repository, answer_repository = clients
    payload = make_payload()
    payload["puzzle"]["clues"][0]["number"] = 9
    payload["officialAnswers"]["answers"] = {"A9": "CAT"}
    response = admin_client.post(SAVE_URL, json=payload)
    assert response.status_code == 400, response.text
    assert puzzle_repository.get_snapshot("puz1") is None
    assert answer_repository.get("puz1") is None


def test_player_save_returns_403_and_does_not_persist(clients):
    _, player_client, puzzle_repository, answer_repository = clients
    response = player_client.post(SAVE_URL, json=make_payload())
    assert response.status_code == 403, response.text
    assert puzzle_repository.get_snapshot("puz1") is None
    assert answer_repository.get("puz1") is None


def test_player_parse_returns_403(clients):
    _, player_client, _, _ = clients
    response = player_client.post(PARSE_URL, json={"use_fixture": True})
    assert response.status_code == 403, response.text


def test_out_of_bounds_cell_returns_422(clients):
    admin_client, _, puzzle_repository, _ = clients
    payload = make_payload()
    payload["puzzle"]["cells"][0]["row"] = 99
    response = admin_client.post(SAVE_URL, json=payload)
    assert response.status_code == 422, response.text
    assert puzzle_repository.get_snapshot("puz1") is None
