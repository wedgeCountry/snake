import random

import pytest

from games.snake.core import SnakeGame
from games.snake.dto import SnakeStateDTO
from games.snake.models import Cell, Direction
from games.snake.config import SnakeConfig


def make_service(seed: int = 1) -> SnakeGame:
    game = SnakeGame(rng=random.Random(seed))
    game.init(SnakeConfig(torus=True, grid_size=10))
    return game


def test_new_game_initial_state():
    game = make_service()
    state = game.state()
    assert state.status == "running"
    assert len(state.snake) == 3
    assert state.score == 0
    assert state.food not in state.snake
    assert state.food.x in range(10)


def test_step_moves_head_forward():
    game = make_service()
    before = game.state().snake[0]
    game.tick()
    after = game.state().snake[0]
    assert after == Cell(before.x + 1, before.y, before.z)
    assert len(game.state().snake) == 3


def test_cannot_reverse_direction():
    game = make_service()
    game.set_direction(Direction(-1, 0, 0))  # opposite of initial (1,0,0)
    assert game.state().direction == Direction(1, 0, 0)


def test_direction_change_applies():
    game = make_service()
    game.set_direction(Direction(0, 0, 1))
    game.tick()
    head = game.state().snake[0]
    assert head.z == 7  # started at z=6, moved +z


def test_wall_collision_kills_when_not_torus():
    game = SnakeGame(rng=random.Random(1))
    game.init(SnakeConfig(torus=False, grid_size=5))
    state = game.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    game.tick()
    assert game.state().status == "dead"


def test_torus_wraps_around():
    game = SnakeGame(rng=random.Random(1))
    game.init(SnakeConfig(torus=True, grid_size=5))
    state = game.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    game.tick()
    assert game.state().status == "running"
    assert game.state().snake[0] == Cell(0, 2, 2)


def test_torus_wraps_vertical():
    game = SnakeGame(rng=random.Random(1))
    game.init(SnakeConfig(torus=True, grid_size=5))
    state = game.state()
    state.snake = [Cell(2, 4, 2), Cell(2, 3, 2), Cell(2, 2, 2)]
    state.direction = Direction(0, 1, 0)
    state.food = Cell(0, 0, 0)
    game.tick()
    assert game.state().snake[0] == Cell(2, 0, 2)


def test_eating_grows_and_scores():
    game = SnakeGame(rng=random.Random(1))
    game.init(SnakeConfig(torus=True, grid_size=5))
    state = game.state()
    state.snake = [Cell(2, 2, 2), Cell(1, 2, 2), Cell(0, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(3, 2, 2)
    game.tick()
    state = game.state()
    assert state.score == 10
    assert len(state.snake) == 4
    assert state.snake[0] == Cell(3, 2, 2)
    assert state.food not in state.snake


def test_self_collision_kills():
    game = SnakeGame(rng=random.Random(1))
    game.init(SnakeConfig(torus=True, grid_size=6))
    state = game.state()
    state.snake = [Cell(2, 2, 2), Cell(2, 3, 2), Cell(3, 3, 2), Cell(3, 2, 2)]
    state.direction = Direction(0, 1, 0)
    state.food = Cell(0, 0, 0)
    game.tick()
    assert game.state().status == "dead"


def test_dead_state_is_stable():
    game = SnakeGame(rng=random.Random(1))
    game.init(SnakeConfig(torus=False, grid_size=5))
    state = game.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    game.tick()
    assert game.state().status == "dead"
    snapshot = game.state().snake.copy()
    game.tick()
    assert game.state().snake == snapshot


def test_step_time_decreases_when_eating():
    game = SnakeGame(rng=random.Random(1))
    game.init(SnakeConfig(torus=True, grid_size=5))
    state = game.state()
    state.step_time_ms = 200
    state.snake = [Cell(2, 2, 2), Cell(1, 2, 2), Cell(0, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(3, 2, 2)
    game.tick()
    assert game.state().step_time_ms == 196


def test_set_torus():
    game = make_service()
    assert game.set_torus(False).torus is False
    assert game.state().torus is False


def test_direction_from_name_invalid():
    with pytest.raises(ValueError):
        Direction.from_name("diagonal")


def test_game_state_serialization_via_dto():
    game = make_service()
    d = SnakeStateDTO.from_state(game.state()).to_dict()
    assert d["snake"][0] == {"x": 3, "y": 5, "z": 6}
    assert "food" in d and "status" in d


def test_apply_action_queues_direction():
    game = make_service()
    game.apply_action(0, {"direction": "up"})
    game.tick()
    assert game.state().direction == Direction(0, 1, 0)
