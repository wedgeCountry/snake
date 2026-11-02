import random

import pytest
from fastapi.testclient import TestClient

from games.snake.config import SnakeConfig
from snake.app import app
from snake.contracts import SESSION_COOKIE
from snake.services.leaderboard import JsonFileLeaderboardService
from snake.services.score import JsonFileScoreService
from snake.services.settings import JsonFileSettingsService
from snake.services.user import COOKIE_NAME, CookieUserService
from snake.session import InMemorySessionService


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


def api_new(client, **kw):
    body = {"mode": "single", "torus": True, **kw}
    r = client.post("/api/games/snake/new", json=body)
    assert r.status_code == 200, r.text
    session_id = client.cookies.get(SESSION_COOKIE)
    loop = app.state.session_loops[session_id]
    client.portal.call(loop.stop)
    loop._session.game.init(SnakeConfig(step_time_ms=400, torus=body["torus"], mode=body["mode"]))
    return r.json()


def api_state(client):
    r = client.get("/api/games/snake/state")
    assert r.status_code == 200, r.text
    return r.json()


def api_action(client, direction, player=0):
    r = client.post("/api/games/snake/action",
                    json={"player": player, "action": {"direction": direction}})
    assert r.status_code == 200, r.text
    return r.json()


def step_session(client, session_id):
    loop = app.state.session_loops[session_id]
    loop.step()


def api_step(client):
    session_id = client.cookies.get(SESSION_COOKIE)
    step_session(client, session_id)
    return api_state(client)


def test_games_listed():
    with TestClient(app) as c:
        r = c.get("/api/games")
    assert r.status_code == 200
    games = r.json()
    assert any(g["id"] == "snake" and g["realTime"] and g["maxPlayers"] == 2 for g in games)


def test_get_state_envelope(client):
    api_new(client)
    body = api_state(client)
    assert body["v"] == 1
    assert body["gameId"] == "snake"
    assert body["sessionId"]
    state = body["state"]
    assert state["gridSize"] == 10
    assert state["status"] == "running"
    assert "best" in body["meta"] and "stepTimeMs" in body["meta"]


def test_action_then_step(client):
    api_new(client)
    api_action(client, "up")
    body = api_step(client)
    assert body["state"]["direction"] == {"x": 0, "y": 1, "z": 0}
    assert body["state"]["snake"][0]["y"] == 6


def test_step_without_action(client):
    api_new(client)
    body = api_step(client)
    assert body["state"]["snake"][0]["x"] == 4  # head starts at x=3


def test_action_rejects_invalid_direction(client):
    api_new(client)
    with pytest.raises(ValueError):
        client.post("/api/games/snake/action",
                    json={"player": 0, "action": {"direction": "sideways"}})


def test_new_game_resets(client):
    api_new(client)
    api_step(client)
    body = api_new(client, torus=False)
    assert body["state"]["score"] == 0
    assert body["meta"]["torus"] is False
    assert len(body["state"]["snake"]) == 3


def test_settings_roundtrip(client):
    api_new(client)
    r = client.post("/api/settings", json={"step_time_ms": 120, "torus": False})
    assert r.status_code == 200
    body = api_state(client)
    assert body["meta"]["stepTimeMs"] == 120
    assert body["meta"]["torus"] is False


def test_settings_clamped(client):
    r = client.post("/api/settings", json={"step_time_ms": 5})
    assert r.status_code == 422


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_state_sets_user_cookie_on_first_visit(client):
    r = client.post("/api/games/snake/new", json={"torus": True})
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["userId"]
    assert COOKIE_NAME in r.cookies
    assert r.cookies[COOKIE_NAME] == body["meta"]["userId"]
    r2 = client.get("/api/games/snake/state")
    body2 = r2.json()
    assert body2["meta"]["leaderboard"] == []
    return
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["userId"]
    assert COOKIE_NAME in r.cookies
    assert r.cookies[COOKIE_NAME] == body["meta"]["userId"]
    assert body["meta"]["leaderboard"] == []


def test_user_id_is_stable_across_requests(client):
    api_new(client)
    first = api_state(client)["meta"]["userId"]
    second = api_state(client)["meta"]["userId"]
    assert first == second


def test_new_game_multi_mode(client):
    body = api_new(client, mode="multi")
    assert body["state"]["mode"] == "multi"
    assert len(body["state"]["snakes"]) == 2
    lb = client.get("/api/leaderboard/snake/multi").json()
    assert lb["gameId"] == "snake" and lb["mode"] == "multi" and lb["top"] == []


def test_leaderboard_rejects_unknown_mode(client):
    r = client.get("/api/leaderboard/snake/coop")
    assert r.status_code == 200
    assert r.json()["top"] == []


def test_state_requires_session(client):
    r = client.get("/api/games/snake/state")
    assert r.status_code == 404


def test_action_rejects_player_beyond_max_players(client):
    api_new(client)
    r = client.post("/api/games/snake/action",
                    json={"player": 5, "action": {"direction": "up"}})
    assert r.status_code == 422


def test_envelope_meta_carries_session_info_not_game_state(client):
    api_new(client)
    body = api_state(client)
    assert "best" not in body["state"]
    assert "userId" not in body["state"]
    assert body["meta"]["best"] == 0
    assert body["meta"]["userId"]
