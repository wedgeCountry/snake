"""Integration tests for the dungeon game through the generic HTTP API.

Covers the dungeon's own controls end-to-end: direction actions steer the
party immediately (including a 180-degree reversal, which snake's input
queue would reject) and invalid directions are rejected; and the level is
generated once at game start and stays static while playing (no mid-game
spawns). Stepping is done via the session loop, the server-side path."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.app import app
from server.contracts import SESSION_COOKIE
from server.services.leaderboard import SqliteLeaderboardService
from server.services.savegame import SqliteSavegameService
from server.services.score import SqliteScoreService
from server.services.settings import SqliteSettingsService
from server.services.user import CookieUserService
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


def _new_dungeon(client) -> None:
    client.post("/api/settings", json={"step_time_ms": 400})
    r = client.post("/api/games/dungeon/new", json={"torus": False, "mode": "single"})
    assert r.status_code == 200
    session_id = client.cookies.get(SESSION_COOKIE)
    client.portal.call(app.state.session_loops[session_id].stop)  # step manually


def _game(client):
    session_id = client.cookies.get(SESSION_COOKIE)
    return app.state.session_loops[session_id]._session.game


def _step(client) -> None:
    session_id = client.cookies.get(SESSION_COOKIE)
    app.state.session_loops[session_id].step()


def _action(client, action: dict) -> int:
    return client.post("/api/games/dungeon/action",
                       json={"player": 0, "action": action}).status_code


def _state(client) -> dict:
    return client.get("/api/games/dungeon/state").json()["state"]


def _party_cell(state: dict) -> tuple[int, int]:
    leader = state["party"][0]
    return leader["x"], leader["y"]


def test_direction_actions_steer_the_party_via_api(client):
    _new_dungeon(client)
    game = _game(client)
    for m in game.state().party:
        m["x"], m["y"] = 3, 3
    assert _action(client, {"direction": "right"}) == 200
    _step(client)
    assert _party_cell(_state(client)) == (4, 3)
    assert all((m["x"], m["y"]) == (4, 3) for m in _state(client)["party"]), \
        "the whole party follows the leader"


def test_180_degree_reversal_is_allowed_via_api(client):
    """The dungeon's own controls are last-write-wins: after drifting right,
    a 'left' action turns the party around immediately (snake's queue would
    reject the reversal)."""
    _new_dungeon(client)
    game = _game(client)
    for m in game.state().party:
        m["x"], m["y"] = 3, 3
    _step(client)  # no input: drifts right
    assert _party_cell(_state(client)) == (4, 3)
    assert _action(client, {"direction": "left"}) == 200
    _step(client)
    assert _party_cell(_state(client)) == (3, 3), "reversal applied on the next tick"


def test_invalid_direction_action_is_rejected(client):
    _new_dungeon(client)
    # apply_action raises ValueError (the shared Game contract); the test
    # client surfaces it directly
    with pytest.raises(ValueError):
        _action(client, {"direction": "not-a-direction"})
    with pytest.raises(ValueError):
        _action(client, {"teleport": "nowhere"})


def test_level_stays_static_throughout_the_game_via_api(client):
    _new_dungeon(client)
    game = _game(client)
    for m in game.state().party:
        m["hp"] = m["max_hp"] = 100000  # survive whatever we walk into
    before = _state(client)
    turn0 = before["turn"]
    cells0 = (set((m["x"], m["y"]) for m in before["monsters"]),
              set(tuple(p) for p in before["potions"]))
    dirs = ["left", "right", "up", "down"]
    for i in range(60):
        _action(client, {"direction": dirs[i % 4]})
        _step(client)
    after = _state(client)
    assert after["turn"] - turn0 == 60 and after["status"] == "running"
    # monsters may die in combat and potions may be drunk, but nothing new
    # may appear: every remaining entity was already in the generated level
    assert set((m["x"], m["y"]) for m in after["monsters"]) <= cells0[0], \
        "no monster spawned during 60 turns"
    assert set(tuple(p) for p in after["potions"]) <= cells0[1], \
        "no potion spawned during 60 turns"


def test_enchant_action_via_api(client):
    _new_dungeon(client)
    game = _game(client)
    game.state().party[0]["gold"] = 50
    assert _action(client, {"enchant": "fire"}) == 200
    state = _state(client)
    assert state["party"][0]["weapon"]["enchant"]["school"] == "fire"
    assert state["party"][0]["gold"] == 40
