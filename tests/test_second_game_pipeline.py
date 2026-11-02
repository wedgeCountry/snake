"""Phase 8 proof: the second game passes the contract suite via the generic
routes, and its score lands on the correct per-game leaderboard."""

import pytest
from fastapi.testclient import TestClient

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


def test_second_game_registered():
    with TestClient(app) as c:
        games = c.get("/api/games").json()
    ids = {g["id"] for g in games}
    assert {"snake", "collector"} <= ids


def test_collector_end_to_end_via_api(client):
    r = client.post("/api/games/collector/new", json={"torus": True})
    assert r.status_code == 200
    env = r.json()
    assert env["gameId"] == "collector"
    assert env["v"] == 1
    assert env["state"]["score"] == 0
    session_id = client.cookies.get(SESSION_COOKIE)
    loop = app.state.session_loops[session_id]
    client.portal.call(loop.stop)

    game = loop._session.game
    # walk onto a dot deterministically
    dots = list(game.state().dots)
    target = dots[0]
    pos = game.state().pos
    while game.state().pos != target:
        dx = target[0] - game.state().pos[0]
        dy = target[1] - game.state().pos[1]
        name = "right" if dx > 0 else "left" if dx < 0 else "up" if dy > 0 else "down"
        r = client.post("/api/games/collector/action",
                        json={"player": 0, "action": {"direction": name}})
        assert r.status_code == 200
        loop.step()
    assert game.state().score >= 10  # ate at least the target dot

    # terminal: fill the board by eating everything, then submit to leaderboard
    state = game.state()
    state.dots = []
    state.status = "running"
    loop._submitted = False
    loop.step()  # eats nothing; drive to terminal by wall
    # force terminal and check per-game leaderboard isolation
    state.status = "dead"
    loop._submitted = False
    loop.step()
    lb = client.get("/api/leaderboard/collector/single").json()
    assert lb["gameId"] == "collector"
    assert lb["top"][0]["score"] == game.state().score
    lb_snake = client.get("/api/leaderboard/snake/single").json()
    assert lb_snake["top"] == []


def test_session_cookie_is_scoped_to_its_game(client):
    # page load auto-starts the first game (collector); selecting snake must
    # not receive the collector session's state
    r = client.post("/api/games/collector/new", json={"torus": True})
    assert r.status_code == 200
    session_id = client.cookies.get(SESSION_COOKIE)
    client.portal.call(app.state.session_loops[session_id].stop)

    assert client.get("/api/games/snake/state").status_code == 404
    r = client.post("/api/games/snake/action",
                    json={"player": 0, "action": {"direction": "up"}})
    assert r.status_code == 404

    # starting snake with the same cookie still works and returns snake state
    r = client.post("/api/games/snake/new", json={"torus": True, "mode": "single"})
    assert r.status_code == 200
    env = r.json()
    assert env["gameId"] == "snake"
    assert "snake" in env["state"]
    client.portal.call(app.state.session_loops[client.cookies.get(SESSION_COOKIE)].stop)
