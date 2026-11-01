import random

import pytest
from fastapi.testclient import TestClient

from snake.app import app
from snake.dependencies import override_services
from snake.services import InMemoryGameService, JsonFileScoreService, JsonFileSettingsService


class NoopLoop:
    """Loop stub: keeps the background loop out of API tests while
    still serving /api/step by delegating to the game service."""

    running = False

    def __init__(self, game):
        self._game = game

    def activate(self) -> None: ...

    def step(self, action=None):
        from snake.models import APIGameState, Direction
        if action is not None:
            self._game.set_direction(Direction.from_name(action))
        return APIGameState.from_state(self._game.step())

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


@pytest.fixture()
def client(tmp_path, monkeypatch):
    game = InMemoryGameService(rng=random.Random(7))
    game.new_game(torus=True, grid_size=10)
    override_services(
        game=game,
        score=JsonFileScoreService(tmp_path / "scores.json"),
        settings=JsonFileSettingsService(tmp_path / "settings.json"),
        loop=NoopLoop(game),
    )
    with TestClient(app) as c:
        yield c


def test_get_state(client):
    r = client.get("/api/state")
    assert r.status_code == 200
    body = r.json()
    assert body["gridSize"] == 10
    assert body["status"] == "running"
    assert "best" in body and "stepTimeMs" in body


def test_post_direction_and_step(client):
    r = client.post("/api/direction", json={"direction": "up"})
    assert r.status_code == 200
    r = client.post("/api/step")
    assert r.json()["direction"] == {"x": 0, "y": 1, "z": 0}
    assert r.json()["snake"][0]["y"] == 6


def test_post_step_with_action(client):
    r = client.post("/api/step", json={"action": "up"})
    assert r.status_code == 200
    body = r.json()
    assert body["direction"] == {"x": 0, "y": 1, "z": 0}
    assert body["snake"][0]["y"] == 6


def test_post_step_without_action(client):
    r = client.post("/api/step")
    assert r.status_code == 200
    assert r.json()["snake"][0]["x"] == 4


def test_post_step_rejects_invalid_action(client):
    r = client.post("/api/step", json={"action": "sideways"})
    assert r.status_code == 422


def test_post_direction_rejects_invalid(client):
    r = client.post("/api/direction", json={"direction": "sideways"})
    assert r.status_code == 422


def test_new_game_resets(client):
    client.post("/api/step")
    r = client.post("/api/new", json={"torus": False})
    body = r.json()
    assert body["score"] == 0
    assert body["torus"] is False
    assert len(body["snake"]) == 3


def test_gameover_submits_score(client):
    r = client.post("/api/gameover")
    assert r.status_code == 200
    assert r.json()["best"] == 0


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
