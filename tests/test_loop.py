"""Tests for the session-scoped loop and the direction queue."""

import asyncio
import random
from pathlib import Path

from games.snake.config import SnakeConfig
from games.snake.core import SnakeGame
from games.snake.dto import SnakeStateDTO
from games.snake.models import Cell, Direction
from server.services.score import JsonFileScoreService
from server.session import InMemorySessionService, SessionLoop


def make_game(seed: int = 1) -> SnakeGame:
    game = SnakeGame(rng=random.Random(seed))
    game.init(SnakeConfig(torus=True, grid_size=10))
    return game


def make_session(game: SnakeGame, score, leaderboard=None, user_id="u1", mode="single"):
    sessions = InMemorySessionService()
    sid = sessions.create("snake", user_id, mode)
    session = sessions.get(sid)
    session.game = game
    return session


def test_direction_queue_applies_one_per_step():
    game = make_game()
    game.set_direction(Direction(0, 1, 0))
    game.set_direction(Direction(0, 0, 1))
    game.tick()
    assert game.state().direction == Direction(0, 1, 0)
    game.tick()
    assert game.state().direction == Direction(0, 0, 1)


def test_direction_queue_rejects_reverse_of_queued():
    game = make_game()
    game.set_direction(Direction(0, 1, 0))
    game.set_direction(Direction(0, -1, 0))  # opposite of queued 'up'
    assert game.state().direction == Direction(1, 0, 0)
    game.tick()
    assert game.state().direction == Direction(0, 1, 0)


def test_direction_queue_capped():
    game = make_game()
    dirs = [Direction(0, 1, 0), Direction(0, 0, 1), Direction(-1, 0, 0), Direction(0, -1, 0), Direction(0, 0, -1)]
    for d in dirs:
        game.set_direction(d)
    game.tick()
    assert game.state().direction == Direction(0, 1, 0)
    game.tick()
    assert game.state().direction == Direction(0, 0, 1)
    game.tick()
    assert game.state().direction == Direction(-1, 0, 0)
    game.tick()
    assert game.state().direction == Direction(0, -1, 0)


def test_loop_steps_while_active(tmp_path: Path):
    game = make_game()
    score = JsonFileScoreService(tmp_path / "scores.json")
    session = make_session(game, score)
    loop = SessionLoop(session, score)
    game.state().step_time_ms = 5

    async def run():
        await loop.start()
        await asyncio.sleep(0.06)
        await loop.stop()

    asyncio.run(run())
    assert game.state().snake[0].x > 3


def test_loop_step_with_action(tmp_path: Path):
    game = make_game()
    score = JsonFileScoreService(tmp_path / "scores.json")
    session = make_session(game, score)
    loop = SessionLoop(session, score)
    loop.step({"direction": "up", "player": 0})
    assert game.state().direction == Direction(0, 1, 0)
    assert game.state().snake[0].y == 6


def test_loop_step_without_action(tmp_path: Path):
    game = make_game()
    score = JsonFileScoreService(tmp_path / "scores.json")
    session = make_session(game, score)
    loop = SessionLoop(session, score)
    loop.step(None)
    assert game.state().direction == Direction(1, 0, 0)
    assert game.state().snake[0].x == 4


def test_loop_step_rejects_invalid_action(tmp_path: Path):
    game = make_game()
    score = JsonFileScoreService(tmp_path / "scores.json")
    session = make_session(game, score)
    loop = SessionLoop(session, score)
    import pytest
    with pytest.raises(ValueError):
        loop.step({"direction": "diagonal"})


def test_snapshot_and_dto():
    game = make_game()
    state = game.state()
    snap = state.snapshot()
    assert snap.snake == state.snake
    assert snap.food == state.food
    assert snap.score == state.score
    assert snap.status == "running"
    d = SnakeStateDTO.from_state(snap).to_dict()
    assert d["snake"][0] == {"x": 3, "y": 5, "z": 6}
    assert "food" in d and "status" in d
    # snapshot is independent of later mutation
    state.score = 99
    assert snap.score == 0


def test_loop_submits_score_on_death(tmp_path: Path):
    game = SnakeGame(rng=random.Random(1))
    game.init(SnakeConfig(torus=False, grid_size=5))
    state = game.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    state.score = 30
    state.step_time_ms = 5
    score = JsonFileScoreService(tmp_path / "scores.json")
    session = make_session(game, score)
    loop = SessionLoop(session, score)

    async def run():
        await loop.start()
        for _ in range(40):
            await asyncio.sleep(0.01)
            if game.state().status != "running":
                break
        await loop.stop()

    asyncio.run(run())
    assert game.state().status == "dead"
    assert score.get_best("snake") == 30
