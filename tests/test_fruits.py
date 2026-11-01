"""Tests for fruit kinds: apple, reverse, grow/shrink grid, star."""

import random

from snake.models import FRUIT_DURATION_S, Cell, Direction, Fruit, FruitKind
from snake.core.game import (
    GRID_RESIZE_STEP,
    MAX_GRID_SIZE,
    MIN_GRID_SIZE,
    STAR_STEPS,
    InMemoryGameService,
)


def make_service(seed: int = 1, grid_size: int = 10) -> InMemoryGameService:
    svc = InMemoryGameService(rng=random.Random(seed))
    svc.new_game(torus=True, grid_size=grid_size)
    return svc


def place_fruit(svc, kind, cell):
    state = svc.state()
    state.food = Fruit(Cell(*cell), kind)


def step_onto(svc, kind, target, direction):
    """Position the snake one cell before target and step onto the fruit."""
    state = svc.state()
    d = Direction(*direction)
    head = Cell(target[0] - d.x, target[1] - d.y, target[2] - d.z)
    state.snake = [head, Cell(head.x - d.x, head.y - d.y, head.z - d.z), Cell(head.x - 2 * d.x, head.y - 2 * d.y, head.z - 2 * d.z)]
    state.direction = d
    place_fruit(svc, kind, target)
    svc.step()
    return svc.state()


def test_new_game_spawns_kinded_fruit():
    svc = make_service()
    state = svc.state()
    assert isinstance(state.food, Fruit)
    assert state.food.kind in set(FruitKind)
    assert state.food.cell not in state.snake


def test_food_serialization_includes_kind():
    svc = make_service()
    d = svc.state().to_dict()
    assert "kind" in d["food"]
    assert d["food"]["kind"] in {k.value for k in FruitKind}
    assert "starSteps" in d


def test_apple_grows_and_scores():
    svc = make_service()
    state = step_onto(svc, FruitKind.APPLE, (3, 2, 2), (1, 0, 0))
    assert state.score == 10
    assert len(state.snake) == 4
    assert state.snake[0] == Cell(3, 2, 2)


def test_reverse_fruit_reverts_direction():
    svc = make_service()
    state = svc.state()
    place_fruit(svc, FruitKind.REVERSE, (4, 5, 6))
    state.snake = [Cell(3, 5, 6), Cell(2, 5, 6), Cell(1, 5, 6)]
    state.direction = Direction(1, 0, 0)
    svc.step()
    state = svc.state()
    assert state.directions[0] == Direction(-1, 0, 0)
    assert state.scores[0] == 5
    # after the revert the head is the old tail; the next step moves along -x
    assert state.snake[0] == Cell(1, 5, 6)
    svc.step()
    assert svc.state().snake[0] == Cell(0, 5, 6)


def test_grow_grid_expands_grid():
    svc = make_service()
    state = svc.state()
    place_fruit(svc, FruitKind.GROW_GRID, (4, 5, 6))
    state.snake = [Cell(3, 5, 6), Cell(2, 5, 6), Cell(1, 5, 6)]
    state.direction = Direction(1, 0, 0)
    svc.step()
    assert svc.state().grid_size == 10 + GRID_RESIZE_STEP
    assert svc.state().scores[0] == 5


def test_shrink_grid_clamps_snake_and_grid():
    svc = make_service(grid_size=10)
    state = svc.state()
    place_fruit(svc, FruitKind.SHRINK_GRID, (4, 5, 6))
    state.snake = [Cell(3, 5, 6), Cell(2, 5, 6), Cell(1, 5, 6)]
    state.direction = Direction(1, 0, 0)
    svc.step()
    state = svc.state()
    assert state.grid_size == 10 - GRID_RESIZE_STEP
    for c in state.snake:
        assert 0 <= c.x < state.grid_size
        assert 0 <= c.y < state.grid_size
        assert 0 <= c.z < state.grid_size


def test_grid_resize_respects_bounds():
    svc = make_service(grid_size=MAX_GRID_SIZE)
    state = svc.state()
    place_fruit(svc, FruitKind.GROW_GRID, (4, 5, 6))
    state.snake = [Cell(3, 5, 6), Cell(2, 5, 6), Cell(1, 5, 6)]
    state.direction = Direction(1, 0, 0)
    svc.step()
    assert svc.state().grid_size == MAX_GRID_SIZE

    svc2 = make_service(grid_size=MIN_GRID_SIZE)
    state2 = svc2.state()
    place_fruit(svc2, FruitKind.SHRINK_GRID, (4, 2, 3))
    state2.snake = [Cell(3, 2, 3), Cell(2, 2, 3), Cell(1, 2, 3)]
    state2.direction = Direction(1, 0, 0)
    svc2.step()
    assert svc2.state().grid_size == MIN_GRID_SIZE


def test_star_makes_snake_pass_through_itself():
    svc = make_service(grid_size=8)
    state = step_onto(svc, FruitKind.STAR, (3, 2, 2), (1, 0, 0))
    # step_onto placed head at (2,2,2) with body at (1,2,2),(0,2,2); after
    # eating the star the snake grew and star_steps was decremented once
    assert state.status == "running"
    assert state.star_steps[0] == STAR_STEPS
    assert state.scores[0] == 15
    # now drive into own body while starred: must survive
    state.snake = [Cell(2, 2, 2), Cell(2, 3, 2), Cell(3, 3, 2), Cell(3, 2, 2)]
    state.direction = Direction(0, 1, 0)  # into (2,3,2) which is body
    svc.step()
    assert svc.state().status == "running"


def test_star_expires_and_self_collision_kills_afterwards():
    svc = make_service(grid_size=8)
    state = step_onto(svc, FruitKind.STAR, (3, 2, 2), (1, 0, 0))
    assert state.star_steps[0] == STAR_STEPS
    state.star_steps[0] = 1  # one more starred step, then it expires
    # burn the last starred step harmlessly
    state.direction = Direction(0, 0, 1)
    state.snake = [Cell(2, 2, 2), Cell(2, 2, 3), Cell(2, 2, 4), Cell(2, 2, 5)]
    svc.step()
    assert svc.state().star_steps[0] == 0
    # now a self-collision kills
    state = svc.state()
    state.snake = [Cell(2, 2, 2), Cell(2, 3, 2), Cell(3, 3, 2), Cell(3, 2, 2)]
    state.direction = Direction(0, 1, 0)
    state.food = Fruit(Cell(0, 0, 0), FruitKind.APPLE)
    svc.step()
    assert svc.state().status == "dead"


def test_star_does_not_save_from_walls_in_non_torus():
    svc = InMemoryGameService(rng=random.Random(1))
    svc.new_game(torus=False, grid_size=5)
    state = svc.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Fruit(Cell(0, 0, 0), FruitKind.APPLE)
    state.star_steps[0] = STAR_STEPS
    svc.step()
    assert svc.state().status == "dead"


def test_respawned_fruit_has_a_kind_and_free_cell():
    svc = make_service(grid_size=5)
    state = svc.state()
    state.snake = [Cell(2, 2, 2), Cell(1, 2, 2), Cell(0, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Fruit(Cell(3, 2, 2), FruitKind.APPLE)
    svc.step()
    new_food = svc.state().food
    assert isinstance(new_food, Fruit)
    assert new_food.kind in set(FruitKind)
    assert new_food.cell not in svc.state().snake
    assert new_food.cell != Cell(3, 2, 2)


def test_fruit_cell_assignment_coerces_to_fruit():
    svc = make_service()
    state = svc.state()
    state.food = Cell(1, 1, 1)
    assert isinstance(state.food, Fruit)
    assert state.food.kind == FruitKind.APPLE
    assert state.food.cell == Cell(1, 1, 1)


def test_fruit_durations_default_forever_only_for_apple():
    assert FRUIT_DURATION_S[FruitKind.APPLE] is None
    for kind in (FruitKind.REVERSE, FruitKind.GROW_GRID, FruitKind.SHRINK_GRID, FruitKind.STAR):
        assert FRUIT_DURATION_S[kind] == 30.0


def test_serialized_fruit_duration():
    svc = make_service()
    state = svc.state()
    d = state.to_dict()
    assert d["fruitAgeMs"] == 0
    expected = state.fruit_duration_ms()
    assert d["fruitDurationMs"] == expected
    state.food = Fruit(Cell(0, 0, 0), FruitKind.APPLE)
    assert state.to_dict()["fruitDurationMs"] is None


def test_timed_fruit_despawns_after_duration():
    svc = make_service()
    state = svc.state()
    old_food = state.food
    state.food = Fruit(Cell(0, 0, 0), FruitKind.STAR)
    state.step_time_ms = 260
    steps = 0
    while state.food.kind == FruitKind.STAR and steps < 200:
        svc.step()
        state = svc.state()
        steps += 1
    # 30s at 260ms/step -> despawn after ~116 steps
    assert 115 <= steps <= 117
    assert state.food.cell != Cell(0, 0, 0) or state.food.kind != FruitKind.STAR


def test_apple_never_despawns():
    svc = make_service()
    state = svc.state()
    state.food = Fruit(Cell(0, 0, 0), FruitKind.APPLE)
    state.step_time_ms = 260
    for _ in range(200):
        svc.step()
        assert svc.state().food.cell == Cell(0, 0, 0)
        assert svc.state().food.kind == FruitKind.APPLE


def test_eating_resets_fruit_age():
    svc = make_service()
    state = svc.state()
    state.food = Fruit(Cell(3, 5, 6), FruitKind.STAR)
    state.fruit_age_ms = 29_000
    state.snake = [Cell(2, 5, 6), Cell(1, 5, 6), Cell(0, 5, 6)]
    state.direction = Direction(1, 0, 0)
    svc.step()
    state = svc.state()
    assert state.fruit_age_ms == 0
    assert state.star_steps[0] == 8
