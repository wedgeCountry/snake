import random

import pytest

from snake.models import Cell, Direction, GameState
from snake.services import InMemoryGameService


def make_service(seed: int = 1) -> InMemoryGameService:
    svc = InMemoryGameService(rng=random.Random(seed))
    svc.new_game(torus=True, grid_size=10)
    return svc


def test_new_game_initial_state():
    svc = make_service()
    state = svc.state()
    assert state.status == "running"
    assert len(state.snake) == 3
    assert state.score == 0
    assert state.food not in state.snake
    assert state.food.x in range(10)


def test_step_moves_head_forward():
    svc = make_service()
    before = svc.state().snake[0]
    svc.step()
    after = svc.state().snake[0]
    assert after == Cell(before.x + 1, before.y, before.z)
    assert len(svc.state().snake) == 3


def test_cannot_reverse_direction():
    svc = make_service()
    svc.set_direction(Direction(-1, 0, 0))  # opposite of initial (1,0,0)
    assert svc.state().direction == Direction(1, 0, 0)


def test_direction_change_applies():
    svc = make_service()
    svc.set_direction(Direction(0, 0, 1))
    svc.step()
    head = svc.state().snake[0]
    assert head.z == 7  # started at z=6, moved +z


def test_wall_collision_kills_when_not_torus():
    svc = InMemoryGameService(rng=random.Random(1))
    svc.new_game(torus=False, grid_size=5)
    # place snake at right edge moving right
    state = svc.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    svc.step()
    assert svc.state().status == "dead"


def test_torus_wraps_around():
    svc = InMemoryGameService(rng=random.Random(1))
    svc.new_game(torus=True, grid_size=5)
    state = svc.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    svc.step()
    assert svc.state().status == "running"
    assert svc.state().snake[0] == Cell(0, 2, 2)


def test_torus_wraps_vertical():
    svc = InMemoryGameService(rng=random.Random(1))
    svc.new_game(torus=True, grid_size=5)
    state = svc.state()
    state.snake = [Cell(2, 4, 2), Cell(2, 3, 2), Cell(2, 2, 2)]
    state.direction = Direction(0, 1, 0)
    state.food = Cell(0, 0, 0)
    svc.step()
    assert svc.state().snake[0] == Cell(2, 0, 2)


def test_eating_grows_and_scores():
    svc = InMemoryGameService(rng=random.Random(1))
    svc.new_game(torus=True, grid_size=5)
    state = svc.state()
    state.snake = [Cell(2, 2, 2), Cell(1, 2, 2), Cell(0, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(3, 2, 2)
    svc.step()
    state = svc.state()
    assert state.score == 10
    assert len(state.snake) == 4
    assert state.snake[0] == Cell(3, 2, 2)
    assert state.food not in state.snake


def test_self_collision_kills():
    svc = InMemoryGameService(rng=random.Random(1))
    svc.new_game(torus=True, grid_size=6)
    state = svc.state()
    state.snake = [Cell(2, 2, 2), Cell(2, 3, 2), Cell(3, 3, 2), Cell(3, 2, 2)]
    state.direction = Direction(0, 0, 1)  # will move to (2,2,3)? no...
    # set up so next head hits body: move up into own neck? neck is (2,3,2)
    state.direction = Direction(0, 1, 0)
    state.food = Cell(0, 0, 0)
    svc.step()
    assert svc.state().status == "dead"


def test_dead_state_is_stable():
    svc = InMemoryGameService(rng=random.Random(1))
    svc.new_game(torus=False, grid_size=5)
    state = svc.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    svc.step()
    assert svc.state().status == "dead"
    snapshot = svc.state().snake.copy()
    svc.step()
    assert svc.state().snake == snapshot


def test_step_time_decreases_when_eating():
    svc = InMemoryGameService(rng=random.Random(1))
    svc.new_game(torus=True, grid_size=5)
    state = svc.state()
    state.step_time_ms = 200
    state.snake = [Cell(2, 2, 2), Cell(1, 2, 2), Cell(0, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(3, 2, 2)
    svc.step()
    assert svc.state().step_time_ms == 196


def test_set_torus():
    svc = make_service()
    assert svc.set_torus(False).torus is False
    assert svc.state().torus is False


def test_direction_from_name_invalid():
    with pytest.raises(ValueError):
        Direction.from_name("diagonal")


def test_game_state_serialization():
    svc = make_service()
    d = svc.state().to_dict()
    assert d["gridSize"] == 10
    assert d["snake"][0] == {"x": 3, "y": 5, "z": 6}
    assert d["direction"] == {"x": 1, "y": 0, "z": 0}
