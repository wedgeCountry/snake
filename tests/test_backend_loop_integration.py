"""Pure-Python integration tests for the session-scoped server loop.

These tests run the real SessionLoop via the app lifespan and observe the
game purely through the generic HTTP API. Setup may place snake/food on the
session's game object; all gameplay happens server-side.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from games.snake.models import Cell, Direction
from server.app import app
from server.contracts import SESSION_COOKIE
from server.services.leaderboard import JsonFileLeaderboardService
from server.services.score import JsonFileScoreService
from server.services.settings import JsonFileSettingsService
from server.services.user import CookieUserService
from server.session import InMemorySessionService


@pytest.fixture()
def client(tmp_path):
    app.state.session_service = InMemorySessionService()
    app.state.score_service = JsonFileScoreService(tmp_path / "scores.json")
    app.state.settings_service = JsonFileSettingsService(tmp_path / "settings.json")
    app.state.user_service = CookieUserService()
    app.state.leaderboard_service = JsonFileLeaderboardService(tmp_path / "leaderboard.json")
    app.state.session_loops = {}
    with TestClient(app) as c:
        yield c


def session_game(client):
    session_id = client.cookies.get(SESSION_COOKIE)
    return app.state.session_loops[session_id]._session.game


def api_state(client):
    r = client.get("/api/games/snake/state")
    assert r.status_code == 200
    body = r.json()
    body["state"]["meta"] = body["meta"]
    return body["state"]


def test_server_loop_advances_game_via_api(client):
    client.post("/api/settings", json={"step_time_ms": 60})
    client.post("/api/games/snake/new", json={"torus": True})
    head0 = api_state(client)["snake"][0]
    time.sleep(0.5)
    s = api_state(client)
    head1 = s["snake"][0]
    assert s["status"] == "running"
    assert (head1["x"], head1["y"], head1["z"]) != (head0["x"], head0["y"], head0["z"])
    dist = (head1["x"] - head0["x"]) % s["gridSize"]
    assert 1 <= dist <= 10, f"moved {dist} cells in 0.5s at 60ms step"


def test_direction_change_applies_on_server_tick(client):
    client.post("/api/settings", json={"step_time_ms": 60})
    client.post("/api/games/snake/new", json={"torus": True})
    y0 = api_state(client)["snake"][0]["y"]
    r = client.post("/api/games/snake/action",
                    json={"player": 0, "action": {"direction": "up"}})
    assert r.status_code == 200
    time.sleep(0.4)
    s = api_state(client)
    assert s["direction"] == {"x": 0, "y": 1, "z": 0}
    assert s["snake"][0]["y"] > y0 or (s["snake"][0]["y"] - y0) % 10 > 0
    assert s["status"] == "running"


def test_game_over_submits_best_via_api(client):
    client.post("/api/settings", json={"step_time_ms": 60})
    client.post("/api/games/snake/new", json={"torus": False})
    state = session_game(client).state()
    state.snake = [Cell(9, 5, 5), Cell(8, 5, 5), Cell(7, 5, 5)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    state.score = 50
    deadline = time.time() + 3.0
    s = api_state(client)
    while s["status"] == "running" and time.time() < deadline:
        time.sleep(0.05)
        s = api_state(client)
    assert s["status"] == "dead"
    assert s["meta"]["best"] == 50
    assert app.state.score_service.get_best("snake") == 50
    # loop deactivates: state stays frozen afterwards
    time.sleep(0.3)
    assert api_state(client)["snake"] == s["snake"]


def test_new_game_reactivates_after_death(client):
    client.post("/api/settings", json={"step_time_ms": 60})
    client.post("/api/games/snake/new", json={"torus": False})
    state = session_game(client).state()
    state.snake = [Cell(9, 5, 5), Cell(8, 5, 5), Cell(7, 5, 5)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    deadline = time.time() + 3.0
    while api_state(client)["status"] == "running" and time.time() < deadline:
        time.sleep(0.05)
    assert api_state(client)["status"] == "dead"
    client.post("/api/games/snake/new", json={"torus": True})
    head0 = api_state(client)["snake"][0]
    time.sleep(0.4)
    s = api_state(client)
    assert s["status"] == "running"
    assert (s["snake"][0]["x"], s["snake"][0]["y"], s["snake"][0]["z"]) != (
        head0["x"], head0["y"], head0["z"])
