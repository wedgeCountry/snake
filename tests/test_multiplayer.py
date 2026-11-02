"""Tests for multiplayer mode: two snakes on one board, per-player control."""

import random

import pytest
from fastapi.testclient import TestClient

from games.snake.config import SnakeConfig
from games.snake.core import SnakeGame
from games.snake.models import Cell, Direction
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


def make_multi(seed: int = 1) -> SnakeGame:
    game = SnakeGame(rng=random.Random(seed))
    game.init(SnakeConfig(torus=True, grid_size=10, mode="multi"))
    return game


def test_multi_new_game_starts_two_snakes():
    game = make_multi()
    state = game.state()
    assert state.mode == "multi"
    assert state.num_players == 2
    assert len(state.snakes[0]) == 3
    assert len(state.snakes[1]) == 3
    assert state.snakes[0][0] != state.snakes[1][0]
    assert state.scores == [0, 0]


def test_multi_step_moves_both_snakes():
    game = make_multi()
    h0 = game.state().snakes[0][0]
    h1 = game.state().snakes[1][0]
    game.tick()
    assert game.state().snakes[0][0] == Cell(h0.x + 1, h0.y, h0.z)
    assert game.state().snakes[1][0] == Cell(h1.x - 1, h1.y, h1.z)


def test_per_player_direction_queues():
    game = make_multi()
    game.set_direction(Direction(0, 1, 0), player=1)
    game.tick()
    assert game.state().directions[0] == Direction(1, 0, 0)
    assert game.state().directions[1] == Direction(0, 1, 0)
    game.set_direction(Direction(0, 0, 1), player=0)
    game.tick()
    assert game.state().directions[0] == Direction(0, 0, 1)
    assert game.state().directions[1] == Direction(0, 1, 0)


def test_player2_cannot_reverse():
    game = make_multi()
    game.set_direction(Direction(1, 0, 0), player=1)  # opposite of P2's (-1,0,0)
    game.tick()
    assert game.state().directions[1] == Direction(-1, 0, 0)


def test_cross_snake_collision_kills():
    game = make_multi()
    state = game.state()
    state.snakes[0] = [Cell(3, 5, 5), Cell(2, 5, 5), Cell(1, 5, 5)]
    state.snakes[1] = [Cell(5, 5, 5), Cell(6, 5, 5), Cell(7, 5, 5)]
    state.directions[0] = Direction(1, 0, 0)
    state.directions[1] = Direction(-1, 0, 0)
    state.food = Cell(0, 0, 0)
    game.tick()  # both heads move to (4,5,5) -> head-on collision
    assert game.state().status == "dead"


def test_wall_death_in_multi_sets_loser():
    game = SnakeGame(rng=random.Random(1))
    game.init(SnakeConfig(torus=False, grid_size=10, mode="multi"))
    state = game.state()
    state.snakes[0] = [Cell(9, 5, 5), Cell(8, 5, 5), Cell(7, 5, 5)]
    state.directions[0] = Direction(1, 0, 0)
    state.snakes[1] = [Cell(2, 2, 2), Cell(3, 2, 2), Cell(4, 2, 2)]
    state.directions[1] = Direction(-1, 0, 0)
    state.food = Cell(0, 0, 0)
    game.tick()
    assert game.state().status == "dead"
    assert game.state().loser == 0


def test_multi_scores_independent():
    game = make_multi()
    state = game.state()
    state.snakes[1] = [Cell(5, 5, 5), Cell(6, 5, 5), Cell(7, 5, 5)]
    state.directions[1] = Direction(-1, 0, 0)
    state.food = Cell(4, 5, 5)
    state.snakes[0] = [Cell(1, 1, 1), Cell(0, 1, 1), Cell(0, 0, 1)]
    state.directions[0] = Direction(1, 0, 0)
    game.tick()
    assert game.state().scores[1] == 10
    assert game.state().scores[0] == 0


def test_state_envelope_exposes_snakes_and_mode(client):
    client.post("/api/games/snake/new", json={"torus": True, "mode": "multi"})
    body = client.get("/api/games/snake/state").json()
    state = body["state"]
    assert state["mode"] == "multi"
    assert len(state["snakes"]) == 2
    assert len(state["directions"]) == 2
    assert state["scores"] == [0, 0]
    assert "loser" in state


def test_action_endpoint_accepts_player(client):
    client.post("/api/games/snake/new", json={"torus": True, "mode": "multi"})
    r = client.post("/api/games/snake/action",
                    json={"player": 1, "action": {"direction": "up"}})
    assert r.status_code == 200
    session_id = client.cookies.get(SESSION_COOKIE)
    app.state.session_loops[session_id].step()
    body = client.get("/api/games/snake/state").json()
    assert body["state"]["directions"][1] == {"x": 0, "y": 1, "z": 0}
    r = client.post("/api/games/snake/action",
                    json={"player": 5, "action": {"direction": "up"}})
    assert r.status_code in (200, 422)


def test_single_mode_state_unchanged(client):
    client.post("/api/games/snake/new", json={"torus": True})
    body = client.get("/api/games/snake/state").json()
    assert body["state"]["mode"] == "single"
    assert len(body["state"]["snakes"]) == 1
    assert body["state"]["loser"] is None
