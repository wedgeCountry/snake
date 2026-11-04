"""Tests for the generalized, game-agnostic user/leaderboard mechanics:
per-user cross-game stats endpoint, meta.userBest in envelopes, and
registry-driven config building (generic routes must not import a game)."""

import pytest
from fastapi.testclient import TestClient

from games.registry import get as get_game_info, list_games
from server.app import app
from server.contracts import SESSION_COOKIE
from server.services.leaderboard import SqliteLeaderboardService
from server.services.savegame import SqliteSavegameService
from server.services.score import SqliteScoreService
from server.services.settings import SqliteSettingsService
from server.services.user import COOKIE_NAME, CookieUserService
from server.session import InMemorySessionService


@pytest.fixture()
def client(tmp_path):
    app.state.session_service = InMemorySessionService()
    app.state.score_service = SqliteScoreService(tmp_path / "games.db")
    app.state.settings_service = SqliteSettingsService(tmp_path / "games.db")
    app.state.user_service = CookieUserService()
    app.state.leaderboard_service = SqliteLeaderboardService(tmp_path / "games.db")
    app.state.savegame_service = SqliteSavegameService(tmp_path / "games.db")
    app.state.session_loops = {}
    with TestClient(app) as c:
        yield c


def test_leaderboard_bests_aggregates_across_games(tmp_path):
    lb = SqliteLeaderboardService(tmp_path / "games.db")
    lb.submit("u1", "snake", "single", 100)
    lb.submit("u1", "snake", "multi", 20)
    lb.submit("u1", "territory", "single", 55)
    lb.submit("u2", "snake", "single", 5)
    assert lb.bests("u1") == {"snake": {"single": 100, "multi": 20}, "territory": {"single": 55}}
    assert lb.bests("u2") == {"snake": {"single": 5}}
    assert lb.bests("nobody") == {}


def test_user_stats_endpoint_returns_cross_game_bests(client):
    lb = app.state.leaderboard_service
    lb.submit("u1", "snake", "single", 42)
    r = client.get("/api/users/me/stats")
    assert r.status_code == 200
    body = r.json()
    uid = body["userId"]
    assert uid and body["bests"] == {}
    assert COOKIE_NAME in r.cookies and r.cookies[COOKIE_NAME] == uid
    # same cookie -> same user, and submitted bests show up
    lb.submit(uid, "dungeon", "single", 77)
    body2 = client.get("/api/users/me/stats").json()
    assert body2["userId"] == uid
    assert body2["bests"] == {"dungeon": {"single": 77}}


def test_envelope_meta_carries_user_best(client):
    client.post("/api/games/snake/new", json={"torus": True, "mode": "single"})
    body = client.get("/api/games/snake/state").json()
    assert body["meta"]["userBest"] == 0
    uid = body["meta"]["userId"]
    app.state.leaderboard_service.submit(uid, "snake", "single", 33)
    body2 = client.get("/api/games/snake/state").json()
    assert body2["meta"]["userBest"] == 33
    assert body2["meta"]["best"] == 0  # global best is separate


def test_generic_new_game_uses_registry_build_config(client):
    """The /new route builds config via the game's registered builder — no
    snake imports in the server layer. Territory has no own builder, so the
    default applies the platform step-time setting."""
    client.post("/api/settings", json={"step_time_ms": 120})
    r = client.post("/api/games/territory/new", json={"torus": True, "mode": "single"})
    assert r.status_code == 200, r.text
    assert r.json()["state"]["stepTimeMs"] == 120
    assert r.json()["state"]["gridSize"] == 9  # territory defaults, not snake's


def test_collector_new_game_honors_step_time_setting(client):
    """Collector must honor the platform step-time setting like the other
    games, so the speed slider works for it too."""
    client.post("/api/settings", json={"step_time_ms": 120})
    r = client.post("/api/games/collector/new", json={"torus": True, "mode": "single"})
    assert r.status_code == 200, r.text
    assert r.json()["state"]["stepTimeMs"] == 120
    assert r.json()["state"]["gridSize"] == 8  # collector defaults, not snake's


def test_snake_build_config_maps_settings_and_request():
    info = get_game_info("snake")
    cfg = info.build_config({"stepTimeMs": 150}, "multi", False)
    assert cfg.step_time_ms == 150 and cfg.mode == "multi" and cfg.torus is False
    # garbage settings fall back to the default instead of crashing
    cfg2 = info.build_config({"stepTimeMs": "fast"}, "single", True)
    assert cfg2.step_time_ms == 260


def test_default_build_config_honors_step_time():
    info = get_game_info("dungeon")
    cfg = info.build_config({"stepTimeMs": 90}, "single", True)
    assert cfg.step_time_ms == 90


def test_server_layer_has_no_snake_imports():
    import server.app, server.services.settings, server.services.user, server.schemas
    import inspect
    for mod in (server.app, server.services.settings, server.services.user, server.schemas):
        src = inspect.getsource(mod)
        assert "games.snake" not in src and "SnakeConfig" not in src, mod.__name__


def test_all_games_advertise_metadata_and_builder():
    for g in list_games():
        info = get_game_info(g["id"])
        assert callable(info.build_config)
        assert info.serialize(info.factory(None).init(info.build_config({}, "single", True))) != {}
