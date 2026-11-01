import random

import pytest
from fastapi.testclient import TestClient

from snake.app import app
from snake.core.game import InMemoryGameService
from snake.services.leaderboard import JsonFileLeaderboardService
from snake.services.score import JsonFileScoreService
from snake.services.settings import JsonFileSettingsService
from snake.services.user import COOKIE_NAME, CookieUserService


class NoopLoop:
    """Loop stub: keeps the background asyncio task out of API tests."""

    running = False

    def activate(self) -> None: ...

    def set_context(self, user_id, mode) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


@pytest.fixture()
def client(tmp_path):
    game = InMemoryGameService(rng=random.Random(7))
    game.new_game(torus=True, grid_size=10)
    app.state.game_service = game
    app.state.score_service = JsonFileScoreService(tmp_path / "scores.json")
    app.state.settings_service = JsonFileSettingsService(tmp_path / "settings.json")
    app.state.user_service = CookieUserService()
    app.state.leaderboard_service = JsonFileLeaderboardService(tmp_path / "leaderboard.json")
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


def test_state_sets_user_cookie_on_first_visit(client):
    r = client.get("/api/state")
    assert r.status_code == 200
    body = r.json()
    assert body["userId"]
    assert COOKIE_NAME in r.cookies
    assert r.cookies[COOKIE_NAME] == body["userId"]
    assert body["leaderboard"] == []


def test_user_id_is_stable_across_requests(client):
    first = client.get("/api/state").json()["userId"]
    second = client.get("/api/state").json()["userId"]
    assert first == second


def test_new_game_accepts_mode_and_registers_leaderboard(client):
    r = client.post("/api/new", json={"torus": True, "mode": "multi"})
    assert r.status_code == 200
    lb = client.get("/api/leaderboard/multi").json()
    assert lb["mode"] == "multi"
    assert lb["top"] == []
    lb_single = client.get("/api/leaderboard/single").json()
    assert lb_single["top"] == []


def test_leaderboard_rejects_unknown_mode(client):
    r = client.get("/api/leaderboard/coop")
    assert r.status_code == 422
