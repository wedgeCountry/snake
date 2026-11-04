"""Integration tests: drive the snake only through the generic HTTP API.

Setup may place snake/food via the session's game object, but every move and
direction change goes through the API endpoints; stepping is done via the
session loop (the server-side stepping path).
"""

from __future__ import annotations

import random
from collections import deque

import pytest
from fastapi.testclient import TestClient

from games.snake.config import SnakeConfig
from games.snake.models import Cell, Direction
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


def api_new_game(client, torus=False):
    client.post("/api/settings", json={"step_time_ms": 400})
    r = client.post("/api/games/snake/new", json={"torus": torus})
    assert r.status_code == 200
    session_id = client.cookies.get(SESSION_COOKIE)
    loop = app.state.session_loops[session_id]
    client.portal.call(loop.stop)
    game = loop._session.game
    import random as _r
    game._rng = _r.Random(7)  # fixed seed: deterministic fruit spawns
    game.init(SnakeConfig(step_time_ms=400, torus=torus))
    return r.json()


def api_direction(client, name):
    r = client.post("/api/games/snake/action",
                    json={"player": 0, "action": {"direction": name}})
    assert r.status_code == 200
    return r.json()


def api_state(client):
    r = client.get("/api/games/snake/state")
    assert r.status_code == 200
    return r.json()


def api_step(client):
    session_id = client.cookies.get(SESSION_COOKIE)
    app.state.session_loops[session_id].step()
    return api_state(client)


def place(client, snake, direction, food):
    session_id = client.cookies.get(SESSION_COOKIE)
    state = app.state.session_loops[session_id]._session.game.state()
    state.snake = [Cell(*c) for c in snake]
    state.direction = Direction(*direction)
    state.food = Cell(*food)
    state.status = "running"


DIRECTION_NAMES = ["left", "right", "up", "down", "forward", "back"]
EXPECTED_DELTA = {
    "left": (-1, 0, 0), "right": (1, 0, 0),
    "up": (0, 1, 0), "down": (0, -1, 0),
    "forward": (0, 0, 1), "back": (0, 0, -1),
}


@pytest.mark.parametrize("name", DIRECTION_NAMES)
def test_movement_all_six_directions(client, name):
    api_new_game(client, torus=True)
    initial = (1, 0, 0) if name != "left" else (0, 0, 1)
    head = (3, 5, 5)
    body = [head, (head[0] - initial[0], head[1] - initial[1], head[2] - initial[2]),
            (head[0] - 2 * initial[0], head[1] - 2 * initial[1], head[2] - 2 * initial[2])]
    place(client, body, initial, (0, 0, 0))
    api_direction(client, name)
    before = api_step(client)["state"]
    dx, dy, dz = EXPECTED_DELTA[name]
    head = before["snake"][0]
    assert (head["x"], head["y"], head["z"]) == (3 + dx, 5 + dy, 5 + dz)
    assert before["status"] == "running"


@pytest.mark.parametrize("axis,vec,food_off", [
    ("x", (1, 0, 0), (1, 0, 0)),
    ("y", (0, 1, 0), (0, 1, 0)),
    ("z", (0, 0, 1), (0, 0, 1)),
])
def test_eat_fruit_positive_axis(client, axis, vec, food_off):
    api_new_game(client, torus=True)
    base = (4, 4, 4)
    snake = [base, (base[0] - 1, base[1], base[2]), (base[0] - 2, base[1], base[2])]
    food = (base[0] + food_off[0], base[1] + food_off[1], base[2] + food_off[2])
    place(client, snake, (1, 0, 0), food)
    api_direction(client, {(-1, 0, 0): "left", (1, 0, 0): "right", (0, 1, 0): "up",
                           (0, -1, 0): "down", (0, 0, 1): "forward", (0, 0, -1): "back"}[vec])
    result = api_step(client)["state"]
    assert result["status"] == "running"
    assert result["score"] == 10
    assert len(result["snake"]) == 4
    head = result["snake"][0]
    assert (head["x"], head["y"], head["z"]) == food


@pytest.mark.parametrize("name,vec,food", [
    ("left", (-1, 0, 0), (3, 5, 5)),
    ("down", (0, -1, 0), (4, 4, 5)),
    ("back", (0, 0, -1), (4, 5, 4)),
])
def test_eat_fruit_negative_directions(client, name, vec, food):
    api_new_game(client, torus=True)
    initial = (1, 0, 0) if name != "left" else (0, 1, 0)
    head = (4, 5, 5)
    snake = [head, (head[0] - initial[0], head[1] - initial[1], head[2] - initial[2]),
             (head[0] - 2 * initial[0], head[1] - 2 * initial[1], head[2] - 2 * initial[2])]
    place(client, snake, initial, food)
    api_direction(client, name)
    result = api_step(client)["state"]
    assert result["score"] == 10
    assert len(result["snake"]) == 4
    assert (result["snake"][0]["x"], result["snake"][0]["y"], result["snake"][0]["z"]) == food


def bfs_path(start, goal, blocked, n, torus=False):
    q = deque([start])
    prev = {start: None}
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        for d in [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]:
            nxt = (cur[0] + d[0], cur[1] + d[1], cur[2] + d[2])
            if torus:
                nxt = (nxt[0] % n, nxt[1] % n, nxt[2] % n)
            elif not all(0 <= nxt[i] < n for i in range(3)):
                continue
            if nxt in prev or nxt in blocked:
                continue
            prev[nxt] = cur
            q.append(nxt)
    if goal not in prev:
        return None
    path = []
    node = goal
    while node != start:
        path.append(node)
        node = prev[node]
    path.reverse()
    return path


def dir_name_between(a, b, n, torus=False):
    d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    if torus:
        d = tuple(((d[i] + n) % n) if ((d[i] + n) % n) <= n // 2 else ((d[i] + n) % n) - n for i in range(3))
    return {(-1, 0, 0): "left", (1, 0, 0): "right", (0, 1, 0): "up",
            (0, -1, 0): "down", (0, 0, 1): "forward", (0, 0, -1): "back"}.get(d)


def test_bfs_walk_to_real_fruit_via_api(client):
    state = api_new_game(client, torus=False)["state"]
    n = state["gridSize"]
    for _ in range(3):
        state = api_state(client)["state"]
        start = (state["snake"][0]["x"], state["snake"][0]["y"], state["snake"][0]["z"])
        goal = (state["food"]["x"], state["food"]["y"], state["food"]["z"])
        body = {(c["x"], c["y"], c["z"]) for c in state["snake"][:-1]}
        length_before = len(state["snake"])
        path = bfs_path(start, goal, body, n, torus=False)
        assert path is not None, "fruit unreachable"
        prev = start
        for step_cell in path:
            name = dir_name_between(prev, step_cell, n)
            assert name is not None
            api_direction(client, name)
            state = api_step(client)["state"]
            assert state["status"] == "running"
            prev = step_cell
        head = state["snake"][0]
        assert (head["x"], head["y"], head["z"]) == goal
        assert len(state["snake"]) == length_before + 1
        assert state["score"] >= 5  # fruit eaten (kind may vary with seed)


def test_torus_walk_through_wall_via_api(client):
    api_new_game(client, torus=True)
    place(client, [(9, 5, 5), (8, 5, 5), (7, 5, 5)], (1, 0, 0), (0, 0, 0))
    api_direction(client, "right")
    state = api_step(client)["state"]
    assert state["status"] == "running"
    assert state["snake"][0]["x"] == 0  # wrapped through the wall
