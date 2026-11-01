import random

import pytest
from fastapi.testclient import TestClient

from snake.app import app
from snake.core.game import InMemoryGameService
from snake.services.score import JsonFileScoreService
from snake.services.settings import JsonFileSettingsService


class NoopLoop:
    """Loop stub: keeps the background asyncio task out of API tests."""

    running = False

    def activate(self) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


@pytest.fixture()
def client(tmp_path):
    game = InMemoryGameService(rng=random.Random(7))
    game.new_game(torus=True, grid_size=10)
    app.state.game_service = game
    app.state.score_service = JsonFileScoreService(tmp_path / "scores.json")
    app.state.settings_service = JsonFileSettingsService(tmp_path / "settings.json")
    app.state.game_loop = NoopLoop()
    with TestClient(app) as c:
        c.game = game
        yield c


def api_step(client):
    client.game.step()
    r = client.get("/api/state")
    assert r.status_code == 200
    return r.json()


def test_get_state(client):
    r = client.get("/api/state")
    assert r.status_code == 200
    body = r.json()
    assert body["gridSize"] == 10
    assert body["status"] == "running"
    assert "best" in body and "stepTimeMs" in body


def test_post_direction_then_step(client):
    r = client.post("/api/direction", json={"direction": "up"})
    assert r.status_code == 200
    body = api_step(client)
    assert body["direction"] == {"x": 0, "y": 1, "z": 0}
    assert body["snake"][0]["y"] == 6


def test_step_without_action(client):
    body = api_step(client)
    assert body["snake"][0]["x"] == 4


def test_post_direction_rejects_invalid(client):
    r = client.post("/api/direction", json={"direction": "sideways"})
    assert r.status_code == 422


def test_new_game_resets(client):
    api_step(client)
    r = client.post("/api/new", json={"torus": False})
    body = r.json()
    assert body["score"] == 0
    assert body["torus"] is False
    assert len(body["snake"]) == 3


def test_settings_roundtrip(client):
    r = client.post("/api/settings", json={"step_time_ms": 120, "torus": False})
    assert r.json() == {"stepTimeMs": 120, "torus": False}
    r = client.get("/api/state")
    assert r.json()["stepTimeMs"] == 120
    assert r.json()["torus"] is False


def test_settings_clamped(client):
    r = client.post("/api/settings", json={"step_time_ms": 5})
    assert r.status_code == 422


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
