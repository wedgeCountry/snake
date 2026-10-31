"""Tests for the server-side game loop and the direction queue."""

import asyncio
import random
from pathlib import Path

from snake.loop import GameLoop
from snake.models import Cell, Direction
from snake.services import InMemoryGameService, JsonFileScoreService


def make_game(seed: int = 1) -> InMemoryGameService:
    svc = InMemoryGameService(rng=random.Random(seed))
    svc.new_game(torus=True, grid_size=10)
    return svc


def test_direction_queue_applies_one_per_step():
    svc = make_game()
    svc.set_direction(Direction(0, 1, 0))
    svc.set_direction(Direction(0, 0, 1))
    svc.step()
    assert svc.state().direction == Direction(0, 1, 0)
    svc.step()
    assert svc.state().direction == Direction(0, 0, 1)


def test_direction_queue_rejects_reverse_of_queued():
    svc = make_game()
    svc.set_direction(Direction(0, 1, 0))
    svc.set_direction(Direction(0, -1, 0))  # opposite of queued 'up'
    assert svc.state().direction == Direction(1, 0, 0)
    svc.step()
    assert svc.state().direction == Direction(0, 1, 0)


def test_direction_queue_capped():
    svc = make_game()
    dirs = [Direction(0, 1, 0), Direction(0, 0, 1), Direction(-1, 0, 0), Direction(0, -1, 0), Direction(0, 0, -1)]
    for d in dirs:
        svc.set_direction(d)
    svc.step()
    assert svc.state().direction == Direction(0, 1, 0)
    svc.step()
    assert svc.state().direction == Direction(0, 0, 1)
    svc.step()
    assert svc.state().direction == Direction(-1, 0, 0)
    svc.step()
    assert svc.state().direction == Direction(0, -1, 0)


def test_loop_steps_while_active(tmp_path: Path):
    game = make_game()
    score = JsonFileScoreService(tmp_path / "scores.json")
    loop = GameLoop(game, score)
    loop.activate()
    game.state().step_time_ms = 5

    async def run():
        await loop.start()
        await asyncio.sleep(0.06)
        await loop.stop()

    asyncio.run(run())
    assert game.state().snake[0].x > 3


def test_loop_idles_when_not_active(tmp_path: Path):
    game = make_game()
    score = JsonFileScoreService(tmp_path / "scores.json")
    loop = GameLoop(game, score)
    game.state().step_time_ms = 5

    async def run():
        await loop.start()
        await asyncio.sleep(0.03)
        await loop.stop()

    asyncio.run(run())
    assert game.state().snake[0].x == 3


def test_loop_submits_score_on_death(tmp_path: Path):
    game = InMemoryGameService(rng=random.Random(1))
    game.new_game(torus=False, grid_size=5)
    state = game.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    state.score = 30
    state.step_time_ms = 5
    score = JsonFileScoreService(tmp_path / "scores.json")
    loop = GameLoop(game, score)
    loop.activate()

    async def run():
        await loop.start()
        for _ in range(40):
            await asyncio.sleep(0.01)
            if game.state().status != "running":
                break
        await loop.stop()

    asyncio.run(run())
    assert game.state().status == "dead"
    assert score.get_best() == 30
