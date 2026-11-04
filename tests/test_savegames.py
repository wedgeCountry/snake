"""Savegame tests: SQLite persistence across service instances, and the
dungeon save/load roundtrip over the API."""

import random

import pytest
from fastapi.testclient import TestClient

from games.dungeon.core import DungeonGame
from games.dungeon.config import DungeonConfig
from games.registry import get as get_game_info
from server.app import app
from server.services.leaderboard import SqliteLeaderboardService
from server.services.savegame import SqliteSavegameService
from server.services.score import SqliteScoreService
from server.services.settings import SqliteSettingsService
from server.services.user import CookieUserService
from server.session import InMemorySessionService


@pytest.fixture()
def client(tmp_path):
    db = tmp_path / "games.db"
    app.state.session_service = InMemorySessionService()
    app.state.score_service = SqliteScoreService(db)
    app.state.settings_service = SqliteSettingsService(db)
    app.state.user_service = CookieUserService()
    app.state.leaderboard_service = SqliteLeaderboardService(db)
    app.state.savegame_service = SqliteSavegameService(db)
    app.state.session_loops = {}
    with TestClient(app) as c:
        yield c


def test_schema_definitions_live_in_exactly_one_place(tmp_path):
    """All CREATE TABLE/INDEX statements exist only in services/schema.py, the
    created db contains exactly the tables defined there, and the savegame
    service references the shared SAVEGAMES_TABLE constant."""
    import inspect

    from server.services import db as db_mod
    from server.services import savegame as savegame_mod
    from server.services import schema

    assert "CREATE TABLE" not in inspect.getsource(db_mod), "db.py must not define tables"
    conn = db_mod.connect(tmp_path / "games.db")
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")} - {"sqlite_sequence"}
    assert names == set(schema.TABLES), "db tables drifted from schema.TABLES"
    assert schema.SAVEGAMES_TABLE in inspect.getsource(savegame_mod), \
        "savegame service must reference SAVEGAMES_TABLE from schema.py"
    conn.close()


def test_sqlite_services_persist_across_instances(tmp_path):
    """Data really lives in tables: a fresh service instance over the same
    db file sees everything the previous one wrote."""
    db = tmp_path / "games.db"
    SqliteScoreService(db).submit("snake", 42)
    SqliteSettingsService(db).set_step_time_ms("u1", 120)
    SqliteLeaderboardService(db).submit("u1", "snake", "single", 77)
    SqliteSavegameService(db).save("u1", "dungeon", "single", "run1", {"score": 5})
    # new instances, same file
    assert SqliteScoreService(db).get_best("snake") == 42
    assert SqliteSettingsService(db).get_step_time_ms("u1") == 120
    assert SqliteLeaderboardService(db).get_best("u1", "snake", "single") == 77
    saves = SqliteSavegameService(db).list("u1", "dungeon")
    assert len(saves) == 1 and saves[0]["name"] == "run1"
    assert SqliteSavegameService(db).get("u1", saves[0]["id"])["state"] == {"score": 5}


def test_dungeon_restore_roundtrip():
    g = DungeonGame(rng=random.Random(1))
    g.init(DungeonConfig(difficulty=6))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    wire = get_game_info("dungeon").serialize(g.state())
    g2 = DungeonGame(rng=random.Random(2))
    g2.init(DungeonConfig())
    g2.restore(wire)
    assert get_game_info("dungeon").serialize(g2.state()) == wire


def test_save_list_load_roundtrip_over_api(client):
    r = client.post("/api/games/dungeon/new", json={"torus": True, "mode": "single"})
    assert r.status_code == 200, r.text
    # advance the game a couple of turns so the saved state is non-trivial
    for _ in range(3):
        client.post("/api/games/dungeon/action", json={"player": 0, "action": {"direction": "right"}})
        sid = client.cookies.get("game_session")
        loop = app.state.session_loops[sid]
        client.portal.call(loop.step)
    saved_state = client.get("/api/games/dungeon/state").json()["state"]

    sg = client.post("/api/games/dungeon/save", json={"name": "run1"})
    assert sg.status_code == 200, sg.text
    save_id = sg.json()["id"]

    listing = client.get("/api/games/dungeon/savegames").json()
    assert [s["id"] for s in listing["savegames"]] == [save_id]
    assert listing["savegames"][0]["name"] == "run1"

    # start a fresh game (state differs), then load the savegame
    client.post("/api/games/dungeon/new", json={"torus": True, "mode": "single"})
    r = client.post(f"/api/games/dungeon/load/{save_id}")
    assert r.status_code == 200, r.text
    loaded = r.json()
    assert loaded["gameId"] == "dungeon"
    assert loaded["state"] == saved_state, "load restores the exact saved state"
    assert loaded["status"] == "running"
    # the new session cookie points at the restored session and its loop runs
    assert client.cookies.get("game_session") == loaded["sessionId"]
    assert loaded["sessionId"] in app.state.session_loops


def test_load_rejects_unknown_save_and_wrong_game(client):
    client.post("/api/games/dungeon/new", json={"torus": True, "mode": "single"})
    assert client.post("/api/games/dungeon/load/9999").status_code == 404
    sg = client.post("/api/games/dungeon/save", json={"name": "x"}).json()
    # a savegame is only valid for the game that created it
    assert client.post(f"/api/games/snake/load/{sg['id']}").status_code == 404


def test_load_unsupported_game_is_422(client):
    # collector has no restore(): create a save via a dungeon session is not
    # possible for collector; craft one directly in the service instead
    app.state.savegame_service.save("u", "collector", "single", "x", {"pos": [0, 0]})
    saves = app.state.savegame_service.list("u", "collector")
    # the API user is not "u"; save under the test client's own user id instead
    uid = client.get("/api/users/me/stats").json()["userId"]
    sg = app.state.savegame_service.save(uid, "collector", "single", "x", {"pos": [0, 0]})
    r = client.post(f"/api/games/collector/load/{sg['id']}")
    assert r.status_code == 422
    assert saves  # sanity: direct service save works


def test_delete_savegame(client):
    client.post("/api/games/dungeon/new", json={"torus": True, "mode": "single"})
    sg = client.post("/api/games/dungeon/save", json={"name": "tmp"}).json()
    assert client.delete(f"/api/games/dungeon/savegames/{sg['id']}").json() == {"ok": True}
    assert client.get("/api/games/dungeon/savegames").json()["savegames"] == []
    assert client.delete(f"/api/games/dungeon/savegames/{sg['id']}").status_code == 404
