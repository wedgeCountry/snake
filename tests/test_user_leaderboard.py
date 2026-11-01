"""Tests for the cookie user service and the per-user leaderboards."""

import random
from pathlib import Path

import pytest

from snake.loop import GameLoop
from snake.models import Cell, Direction
from snake.core.game import InMemoryGameService
from snake.services.leaderboard import JsonFileLeaderboardService
from snake.services.score import JsonFileScoreService
from snake.services.user import COOKIE_NAME, CookieUserService


def test_user_ids_are_unique():
    user = CookieUserService()
    ids = {user.new_id() for _ in range(100)}
    assert len(ids) == 100


def test_resolve_keeps_existing_cookie():
    user = CookieUserService()
    assert user.resolve("abc123") == "abc123"
    assert user.resolve(None) != ""
    assert user.cookie_name == COOKIE_NAME


def test_leaderboard_submit_keeps_max_per_user(tmp_path: Path):
    lb = JsonFileLeaderboardService(tmp_path / "leaderboard.json")
    assert lb.submit("u1", "single", 30) == 30
    assert lb.submit("u1", "single", 10) == 30
    assert lb.submit("u1", "single", 50) == 50
    assert lb.get_best("u1", "single") == 50
    assert lb.get_best("u2", "single") == 0


def test_leaderboard_boards_are_independent(tmp_path: Path):
    lb = JsonFileLeaderboardService(tmp_path / "leaderboard.json")
    lb.submit("u1", "single", 100)
    lb.submit("u1", "multi", 20)
    assert lb.get_best("u1", "single") == 100
    assert lb.get_best("u1", "multi") == 20
    assert lb.top("single")[0] == {"userId": "u1", "score": 100}
    assert lb.top("multi")[0] == {"userId": "u1", "score": 20}


def test_leaderboard_top_sorted_and_limited(tmp_path: Path):
    lb = JsonFileLeaderboardService(tmp_path / "leaderboard.json")
    for i in range(15):
        lb.submit(f"u{i}", "multi", i * 10)
    top = lb.top("multi", limit=3)
    assert [t["score"] for t in top] == [140, 130, 120]


def test_leaderboard_persists_across_instances(tmp_path: Path):
    path = tmp_path / "leaderboard.json"
    JsonFileLeaderboardService(path).submit("u1", "single", 42)
    lb = JsonFileLeaderboardService(path)
    assert lb.get_best("u1", "single") == 42


def test_leaderboard_rejects_unknown_mode(tmp_path: Path):
    lb = JsonFileLeaderboardService(tmp_path / "leaderboard.json")
    with pytest.raises(ValueError):
        lb.submit("u1", "coop", 10)
    with pytest.raises(ValueError):
        lb.top("coop")


def test_loop_registers_score_on_leaderboard(tmp_path: Path):
    game = InMemoryGameService(rng=random.Random(1))
    game.new_game(torus=False, grid_size=5)
    state = game.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    state.score = 70
    score = JsonFileScoreService(tmp_path / "scores.json")
    lb = JsonFileLeaderboardService(tmp_path / "leaderboard.json")
    loop = GameLoop(game, score, lb, user_id="u9", mode="multi")
    loop.activate()
    loop.step()
    assert game.state().status == "dead"
    assert lb.get_best("u9", "multi") == 70
    assert lb.get_best("u9", "single") == 0
