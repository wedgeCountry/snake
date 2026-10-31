"""Integration tests: drive the snake only through the real HTTP API.

Setup may place snake/food via the service object, but every move,
direction change and step goes through the API endpoints.
"""

from __future__ import annotations

import random
from collections import deque

import pytest
from fastapi.testclient import TestClient

from snake.app import app
from snake.dependencies import override_services
from snake.models import Cell, Direction
from snake.services import InMemoryGameService, JsonFileScoreService, JsonFileSettingsService

DIRECTION_NAMES = ["left", "right", "up", "down", "forward", "back"]
EXPECTED_DELTA = {
    "left": (-1, 0, 0), "right": (1, 0, 0),
    "up": (0, 1, 0), "down": (0, -1, 0),
    "forward": (0, 0, 1), "back": (0, 0, -1),
}


@pytest.fixture()
def client(tmp_path):
    game = InMemoryGameService(rng=random.Random(42))
    override_services(
        game=game,
        score=JsonFileScoreService(tmp_path / "scores.json"),
        settings=JsonFileSettingsService(tmp_path / "settings.json"),
    )
    with TestClient(app) as c:
        c.game = game
        yield c


def api_new_game(client, torus=False):
    r = client.post("/api/new", json={"torus": torus})
    assert r.status_code == 200
    return r.json()


def api_direction(client, name):
    r = client.post("/api/direction", json={"direction": name})
    assert r.status_code == 200
    return r.json()


def api_step(client):
    r = client.post("/api/step")
    assert r.status_code == 200
    return r.json()


def place(client, snake, direction, food):
    """Fixture-level setup on the service; all gameplay stays on the API."""
    state = client.game.state()
    state.snake = [Cell(*c) for c in snake]
    state.direction = Direction(*direction)
    state.food = Cell(*food)
    state.status = "running"


@pytest.mark.parametrize("name", DIRECTION_NAMES)
def test_movement_all_six_directions(client, name):
    api_new_game(client, torus=True)
    # initial direction must not be opposite to the tested one;
    # body extends behind the head along the initial axis
    initial = (1, 0, 0) if name != "left" else (0, 0, 1)
    head = (3, 5, 5)
    body = [head, (head[0] - initial[0], head[1] - initial[1], head[2] - initial[2]),
            (head[0] - 2 * initial[0], head[1] - 2 * initial[1], head[2] - 2 * initial[2])]
    place(client, body, initial, (0, 0, 0))
    api_direction(client, name)
    before = api_step(client)
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
    result = api_step(client)
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
    result = api_step(client)
    assert result["score"] == 10
    assert len(result["snake"]) == 4
    assert (result["snake"][0]["x"], result["snake"][0]["y"], result["snake"][0]["z"]) == food


def bfs_path(start, goal, blocked, n, torus=False):
    """Shortest path on the grid; blocked = snake body (tail cell allowed)."""
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
        d = tuple((d[i] + n // 2) % n - n // 2 + (n // 2 if (d[i] + n // 2) % n < n // 2 else 0) for i in range(3))
        # simpler: wrap delta into [-n/2, n/2]
        d = tuple(((d[i] + n) % n) if ((d[i] + n) % n) <= n // 2 else ((d[i] + n) % n) - n for i in range(3))
    return {(-1, 0, 0): "left", (1, 0, 0): "right", (0, 1, 0): "up",
            (0, -1, 0): "down", (0, 0, 1): "forward", (0, 0, -1): "back"}.get(d)


def test_bfs_walk_to_real_fruit_via_api(client):
    state = api_new_game(client, torus=False)
    n = state["gridSize"]
    for _ in range(3):
        state = client.get("/api/state").json()
        start = (state["snake"][0]["x"], state["snake"][0]["y"], state["snake"][0]["z"])
        goal = (state["food"]["x"], state["food"]["y"], state["food"]["z"])
        body = {(c["x"], c["y"], c["z"]) for c in state["snake"][:-1]}  # tail will move
        length_before = len(state["snake"])
        path = bfs_path(start, goal, body, n, torus=False)
        assert path is not None, "fruit unreachable"
        prev = start
        for step_cell in path:
            name = dir_name_between(prev, step_cell, n)
            assert name is not None
            api_direction(client, name)
            state = api_step(client)
            assert state["status"] == "running"
            prev = step_cell
        head = state["snake"][0]
        assert (head["x"], head["y"], head["z"]) == goal
        assert len(state["snake"]) == length_before + 1
        assert state["score"] == 10 * (length_before - 2)


def test_torus_walk_through_wall_via_api(client):
    api_new_game(client, torus=True)
    place(client, [(9, 5, 5), (8, 5, 5), (7, 5, 5)], (1, 0, 0), (0, 0, 0))
    api_direction(client, "right")
    state = api_step(client)
    assert state["status"] == "running"
    assert state["snake"][0]["x"] == 0  # wrapped through the wall
