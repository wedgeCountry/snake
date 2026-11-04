"""Tests for the cookie user service, per-user settings, and per-game leaderboards."""

import random
from pathlib import Path

import pytest

from games.snake.config import SnakeConfig
from games.snake.core import SnakeGame
from games.snake.models import Cell, Direction
from server.services.leaderboard import SqliteLeaderboardService
from server.services.score import SqliteScoreService
from server.services.settings import SqliteSettingsService
from server.services.user import COOKIE_NAME, CookieUserService
from server.session import InMemorySessionService, SessionLoop


def test_user_ids_are_unique():
    user = CookieUserService()
    ids = {user.new_id() for _ in range(100)}
    assert len(ids) == 100


def test_resolve_keeps_existing_cookie():
    user = CookieUserService()
    assert user.resolve("abc123") == "abc123"
    assert user.resolve(None) != ""
    assert user.cookie_name == COOKIE_NAME


def test_settings_are_independent_per_user(tmp_path: Path):
    s = SqliteSettingsService(tmp_path / "games.db")
    s.set_step_time_ms("u1", 100)
    s.set_torus("u2", False)
    assert s.get_step_time_ms("u1") == 100
    assert s.get_step_time_ms("u2") == 260  # anonymous default
    assert s.get_torus("u1") is True
    assert s.get_torus("u2") is False
    assert s.get_step_time_ms("anonymous") == 260


def test_score_service_keyed_by_game(tmp_path: Path):
    svc = SqliteScoreService(tmp_path / "games.db")
    assert svc.submit("snake", 30) == 30
    assert svc.submit("other", 99) == 99
    assert svc.get_best("snake") == 30
    assert svc.get_best("other") == 99
    assert svc.get_best("unknown") == 0


def test_leaderboard_submit_keeps_max_per_user(tmp_path: Path):
    lb = SqliteLeaderboardService(tmp_path / "games.db")
    assert lb.submit("u1", "snake", "single", 30) == 30
    assert lb.submit("u1", "snake", "single", 10) == 30
    assert lb.submit("u1", "snake", "single", 50) == 50
    assert lb.get_best("u1", "snake", "single") == 50
    assert lb.get_best("u2", "snake", "single") == 0


def test_leaderboard_boards_are_independent(tmp_path: Path):
    lb = SqliteLeaderboardService(tmp_path / "games.db")
    lb.submit("u1", "snake", "single", 100)
    lb.submit("u1", "snake", "multi", 20)
    lb.submit("u1", "other-game", "single", 5)
    assert lb.get_best("u1", "snake", "single") == 100
    assert lb.get_best("u1", "snake", "multi") == 20
    assert lb.get_best("u1", "other-game", "single") == 5
    assert lb.top("snake", "single")[0] == {"userId": "u1", "score": 100}


def test_leaderboard_top_sorted_and_limited(tmp_path: Path):
    lb = SqliteLeaderboardService(tmp_path / "games.db")
    for i in range(15):
        lb.submit(f"u{i}", "snake", "multi", i * 10)
    top = lb.top("snake", "multi", limit=3)
    assert [t["score"] for t in top] == [140, 130, 120]


def test_leaderboard_persists_across_instances(tmp_path: Path):
    path = tmp_path / "games.db"
    SqliteLeaderboardService(path).submit("u1", "snake", "single", 42)
    lb = SqliteLeaderboardService(path)
    assert lb.get_best("u1", "snake", "single") == 42


def test_leaderboard_rejects_unknown_mode(tmp_path: Path):
    lb = SqliteLeaderboardService(tmp_path / "games.db")
    with pytest.raises(ValueError):
        lb.submit("u1", "snake", "coop", 10)
    with pytest.raises(ValueError):
        lb.top("snake", "coop")


def test_loop_registers_score_on_leaderboard(tmp_path: Path):
    game = SnakeGame(rng=random.Random(1))
    game.init(SnakeConfig(torus=False, grid_size=5, mode="multi"))
    state = game.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    state.score = 70
    score = SqliteScoreService(tmp_path / "games.db")
    lb = SqliteLeaderboardService(tmp_path / "games.db")
    sessions = InMemorySessionService()
    sid = sessions.create("snake", "u9", "multi")
    session = sessions.get(sid)
    session.game = game
    loop = SessionLoop(session, score, lb)
    loop.step()
    assert game.state().status == "dead"
    assert lb.get_best("u9", "snake", "multi") == 70
    assert lb.get_best("u9", "snake", "single") == 0
