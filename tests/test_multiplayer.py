"""Tests for multiplayer mode: two snakes on one board, per-player control."""

import random

import pytest
from fastapi.testclient import TestClient

from snake.app import app
from snake.models import Cell, Direction
from snake.core.game import InMemoryGameService
from snake.services.leaderboard import JsonFileLeaderboardService
from snake.services.score import JsonFileScoreService
from snake.services.settings import JsonFileSettingsService
from snake.services.user import CookieUserService


class NoopLoop:
    running = False

    def activate(self) -> None: ...

    def set_context(self, user_id, mode) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


@pytest.fixture()
def client(tmp_path):
    game = InMemoryGameService(rng=random.Random(7))
    app.state.game_service = game
    app.state.score_service = JsonFileScoreService(tmp_path / "scores.json")
    app.state.settings_service = JsonFileSettingsService(tmp_path / "settings.json")
    app.state.user_service = CookieUserService()
    app.state.leaderboard_service = JsonFileLeaderboardService(tmp_path / "leaderboard.json")
    app.state.game_loop = NoopLoop()
    with TestClient(app) as c:
        c.game = game
        yield c


def make_multi(seed: int = 1) -> InMemoryGameService:
    svc = InMemoryGameService(rng=random.Random(seed))
    svc.new_game(torus=True, grid_size=10, mode="multi")
    return svc


def test_multi_new_game_starts_two_snakes():
    svc = make_multi()
    state = svc.state()
    assert state.mode == "multi"
    assert state.num_players == 2
    assert len(state.snakes[0]) == 3
    assert len(state.snakes[1]) == 3
    assert state.snakes[0][0] != state.snakes[1][0]
    assert state.scores == [0, 0]


def test_multi_step_moves_both_snakes():
    svc = make_multi()
    h0 = svc.state().snakes[0][0]
    h1 = svc.state().snakes[1][0]
    svc.step()
    assert svc.state().snakes[0][0] == Cell(h0.x + 1, h0.y, h0.z)
    assert svc.state().snakes[1][0] == Cell(h1.x - 1, h1.y, h1.z)


def test_per_player_direction_queues():
    svc = make_multi()
    svc.set_direction(Direction(0, 1, 0), player=1)
    svc.step()
    assert svc.state().directions[0] == Direction(1, 0, 0)
    assert svc.state().directions[1] == Direction(0, 1, 0)
    # player 0 queue unaffected by player 1 input
    svc.set_direction(Direction(0, 0, 1), player=0)
    svc.step()
    assert svc.state().directions[0] == Direction(0, 0, 1)
    assert svc.state().directions[1] == Direction(0, 1, 0)


def test_player2_cannot_reverse():
    svc = make_multi()
    svc.set_direction(Direction(1, 0, 0), player=1)  # opposite of P2's (-1,0,0)
    svc.step()
    assert svc.state().directions[1] == Direction(-1, 0, 0)


def test_cross_snake_collision_kills():
    svc = make_multi()
    state = svc.state()
    # place P2's head right in front of P1 so P1 runs into P2's body
    state.snakes[0] = [Cell(3, 5, 5), Cell(2, 5, 5), Cell(1, 5, 5)]
    state.snakes[1] = [Cell(5, 5, 5), Cell(6, 5, 5), Cell(7, 5, 5)]
    state.directions[0] = Direction(1, 0, 0)
    state.directions[1] = Direction(-1, 0, 0)
    state.food = Cell(0, 0, 0)
    svc.step()  # both heads move to (4,5,5) -> head-on collision
    assert svc.state().status == "dead"


def test_wall_death_in_multi_sets_loser():
    svc = InMemoryGameService(rng=random.Random(1))
    svc.new_game(torus=False, grid_size=10, mode="multi")
    state = svc.state()
    state.snakes[0] = [Cell(9, 5, 5), Cell(8, 5, 5), Cell(7, 5, 5)]
    state.directions[0] = Direction(1, 0, 0)
    state.snakes[1] = [Cell(2, 2, 2), Cell(3, 2, 2), Cell(4, 2, 2)]
    state.directions[1] = Direction(-1, 0, 0)
    state.food = Cell(0, 0, 0)
    svc.step()
    assert svc.state().status == "dead"
    assert svc.state().loser == 0


def test_multi_scores_independent():
    svc = make_multi()
    state = svc.state()
    state.snakes[1] = [Cell(5, 5, 5), Cell(6, 5, 5), Cell(7, 5, 5)]
    state.directions[1] = Direction(-1, 0, 0)
    state.food = Cell(4, 5, 5)
    state.snakes[0] = [Cell(1, 1, 1), Cell(0, 1, 1), Cell(0, 0, 1)]
    state.directions[0] = Direction(1, 0, 0)
    svc.step()
    assert svc.state().scores[1] == 10
    assert svc.state().scores[0] == 0


def test_state_dict_exposes_snakes_and_mode(client):
    client.post("/api/new", json={"torus": True, "mode": "multi"})
    body = client.get("/api/state").json()
    assert body["mode"] == "multi"
    assert len(body["snakes"]) == 2
    assert len(body["directions"]) == 2
    assert body["scores"] == [0, 0]
    assert "loser" in body


def test_direction_endpoint_accepts_player(client):
    client.post("/api/new", json={"torus": True, "mode": "multi"})
    r = client.post("/api/direction", json={"direction": "up", "player": 1})
    assert r.status_code == 200
    client.game.step()
    body = client.get("/api/state").json()
    assert body["directions"][1] == {"x": 0, "y": 1, "z": 0}
    r = client.post("/api/direction", json={"direction": "up", "player": 5})
    assert r.status_code == 422


def test_single_mode_state_unchanged(client):
    client.post("/api/new", json={"torus": True})
    body = client.get("/api/state").json()
    assert body["mode"] == "single"
    assert len(body["snakes"]) == 1
    assert body["loser"] is None
