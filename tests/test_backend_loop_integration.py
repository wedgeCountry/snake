"""Pure-Python integration tests for the server-side game loop.

These tests run the real GameLoop via the app lifespan and observe the
game purely through the HTTP API. Setup may place snake/food on the
service object; all gameplay happens server-side.
"""

from __future__ import annotations

import random
import time

import pytest
from fastapi.testclient import TestClient

from snake.app import app
from snake.loop import GameLoop
from snake.models import Cell, Direction
from snake.core.game import InMemoryGameService
from snake.services.score import JsonFileScoreService
from snake.services.settings import JsonFileSettingsService


@pytest.fixture()
def client(tmp_path):
    game = InMemoryGameService(rng=random.Random(42))
    score = JsonFileScoreService(tmp_path / "scores.json")
    settings = JsonFileSettingsService(tmp_path / "settings.json")
    app.state.game_service = game
    app.state.score_service = score
    app.state.settings_service = settings
    app.state.game_loop = GameLoop(game, score)
    with TestClient(app) as c:
        c.game = game
        c.score = score
        yield c


def api_state(client):
    r = client.get("/api/state")
    assert r.status_code == 200
    return r.json()


def test_loop_idles_until_new_game(client):
    client.post("/api/settings", json={"step_time_ms": 60})
    before = api_state(client)
    time.sleep(0.4)
    after = api_state(client)
    assert after["snake"] == before["snake"]


def test_server_loop_advances_game_via_api(client):
    client.post("/api/settings", json={"step_time_ms": 60})
    client.post("/api/new", json={"torus": True})
    head0 = api_state(client)["snake"][0]
    time.sleep(0.5)
    s = api_state(client)
    head1 = s["snake"][0]
    assert s["status"] == "running"
    assert (head1["x"], head1["y"], head1["z"]) != (head0["x"], head0["y"], head0["z"])
    # default direction is +x on a torus: x advances modulo grid size
    assert head1["x"] == (head0["x"] + 1) % s["gridSize"] or head1["x"] > head0["x"]


def test_direction_change_applies_on_server_tick(client):
    client.post("/api/settings", json={"step_time_ms": 60})
    client.post("/api/new", json={"torus": True})
    y0 = api_state(client)["snake"][0]["y"]
    r = client.post("/api/direction", json={"direction": "up"})
    assert r.status_code == 200
    time.sleep(0.4)
    s = api_state(client)
    assert s["direction"] == {"x": 0, "y": 1, "z": 0}
    assert s["snake"][0]["y"] > y0
    assert s["status"] == "running"


def test_game_over_submits_best_via_api(client):
    client.post("/api/settings", json={"step_time_ms": 60})
    client.post("/api/new", json={"torus": False})
    state = client.game.state()
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
    assert s["best"] == 50
    assert client.score.get_best() == 50
    # loop deactivated: state stays frozen afterwards
    time.sleep(0.3)
    assert api_state(client)["snake"] == s["snake"]


def test_new_game_reactivates_loop_after_death(client):
    client.post("/api/settings", json={"step_time_ms": 60})
    client.post("/api/new", json={"torus": False})
    state = client.game.state()
    state.snake = [Cell(9, 5, 5), Cell(8, 5, 5), Cell(7, 5, 5)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    deadline = time.time() + 3.0
    while api_state(client)["status"] == "running" and time.time() < deadline:
        time.sleep(0.05)
    assert api_state(client)["status"] == "dead"
    client.post("/api/new", json={"torus": True})
    head0 = api_state(client)["snake"][0]
    time.sleep(0.4)
    s = api_state(client)
    assert s["status"] == "running"
    assert (s["snake"][0]["x"], s["snake"][0]["y"], s["snake"][0]["z"]) != (
        head0["x"], head0["y"], head0["z"])
