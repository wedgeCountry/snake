import random

from games.snake.config import DEFAULT_DURATIONS_S, STAR_STEPS, SnakeConfig
from games.snake.core import SnakeGame
from games.snake.dto import SnakeStateDTO
from games.snake.models import Cell, Direction, Fruit, FruitKind


def make_service(seed: int = 1, grid_size: int = 10) -> SnakeGame:
    game = SnakeGame(rng=random.Random(seed))
    game.init(SnakeConfig(torus=True, grid_size=grid_size))
    return game


def test_apple_scores_and_grows():
    game = make_service(grid_size=5)
    state = game.state()
    state.snake = [Cell(2, 2, 2), Cell(1, 2, 2), Cell(0, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Fruit(Cell(3, 2, 2), FruitKind.APPLE)
    game.tick()
    assert game.state().score == 10
    assert len(game.state().snake) == 4


def test_reverse_swaps_head_and_tail():
    game = make_service(grid_size=8)
    state = game.state()
    state.snake = [Cell(4, 4, 4), Cell(3, 4, 4), Cell(2, 4, 4)]
    state.direction = Direction(1, 0, 0)
    state.food = Fruit(Cell(5, 4, 4), FruitKind.REVERSE)
    game.tick()
    state = game.state()
    assert state.score == 5
    assert state.direction == Direction(-1, 0, 0)
    assert state.snake[0] == Cell(2, 4, 4)  # old tail is the new head


def test_grow_grid_expands_board():
    game = make_service(grid_size=6)
    state = game.state()
    state.snake = [Cell(2, 3, 3), Cell(1, 3, 3), Cell(0, 3, 3)]
    state.direction = Direction(1, 0, 0)
    state.food = Fruit(Cell(3, 3, 3), FruitKind.GROW_GRID)
    game.tick()
    assert game.state().grid_size == 8
    assert game.state().score == 5


def test_shrink_grid_shrinks_board():
    game = make_service(grid_size=10)
    state = game.state()
    state.snake = [Cell(2, 5, 5), Cell(1, 5, 5), Cell(0, 5, 5)]
    state.direction = Direction(1, 0, 0)
    state.food = Fruit(Cell(3, 5, 5), FruitKind.SHRINK_GRID)
    game.tick()
    assert game.state().grid_size == 8
    assert game.state().score == 5


def test_star_grants_invincibility():
    game = make_service(grid_size=8)
    state = game.state()
    state.snake = [Cell(2, 4, 4), Cell(1, 4, 4), Cell(0, 4, 4)]
    state.direction = Direction(1, 0, 0)
    state.food = Fruit(Cell(3, 4, 4), FruitKind.STAR)
    game.tick()
    assert game.state().score == 15
    assert game.state().star_steps[0] == STAR_STEPS  # set this tick, decrements from next


def test_star_passes_through_own_body():
    game = make_service(grid_size=8)
    state = game.state()
    state.snake = [Cell(2, 2, 2), Cell(2, 3, 2), Cell(3, 3, 2), Cell(3, 2, 2)]
    state.direction = Direction(0, 1, 0)
    state.food = Fruit(Cell(0, 0, 0), FruitKind.APPLE)
    state.star_steps[0] = STAR_STEPS
    game.tick()  # would be self-collision without star
    assert game.state().status == "running"


def test_star_does_not_save_from_walls_in_non_torus():
    game = SnakeGame(rng=random.Random(1))
    game.init(SnakeConfig(torus=False, grid_size=5))
    state = game.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Fruit(Cell(0, 0, 0), FruitKind.APPLE)
    state.star_steps[0] = STAR_STEPS
    game.tick()
    assert game.state().status == "dead"


def test_respawned_fruit_has_a_kind_and_free_cell():
    game = make_service(grid_size=5)
    state = game.state()
    state.snake = [Cell(2, 2, 2), Cell(1, 2, 2), Cell(0, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Fruit(Cell(3, 2, 2), FruitKind.APPLE)
    game.tick()
    new_food = game.state().food
    assert isinstance(new_food, Fruit)
    assert new_food.kind in set(FruitKind)
    assert new_food.cell not in game.state().snake
    assert new_food.cell != Cell(3, 2, 2)


def test_fruit_cell_assignment_coerces_to_fruit():
    game = make_service()
    state = game.state()
    state.food = Cell(1, 1, 1)
    assert isinstance(state.food, Fruit)
    assert state.food.kind == FruitKind.APPLE
    assert state.food.cell == Cell(1, 1, 1)


def test_fruit_durations_default_forever_only_for_apple():
    assert DEFAULT_DURATIONS_S[FruitKind.APPLE] is None
    for kind in (FruitKind.REVERSE, FruitKind.GROW_GRID, FruitKind.SHRINK_GRID, FruitKind.STAR):
        assert DEFAULT_DURATIONS_S[kind] == 30.0


def test_serialized_fruit_duration():
    game = make_service()
    state = game.state()
    d = SnakeStateDTO.from_state(state).to_dict()
    assert d["fruitAgeMs"] == 0
    assert d["fruitDurationMs"] == (None if state.food.kind == FruitKind.APPLE else 30000)
    state.food = Fruit(Cell(0, 0, 0), FruitKind.APPLE)
    assert SnakeStateDTO.from_state(state).to_dict()["fruitDurationMs"] is None


def test_timed_fruit_despawns_after_duration():
    game = make_service()
    state = game.state()
    state.food = Fruit(Cell(0, 0, 0), FruitKind.STAR)
    state.step_time_ms = 260
    steps = 0
    while state.food.kind == FruitKind.STAR and steps < 200:
        game.tick()
        state = game.state()
        steps += 1
    # 30s at 260ms/step -> despawn after ~116 steps
    assert 115 <= steps <= 117
    assert state.food.cell != Cell(0, 0, 0) or state.food.kind != FruitKind.STAR


def test_apple_never_despawns():
    game = make_service()
    state = game.state()
    state.food = Fruit(Cell(0, 0, 0), FruitKind.APPLE)
    state.step_time_ms = 260
    for _ in range(200):
        game.tick()
        assert game.state().food.cell == Cell(0, 0, 0)
        assert game.state().food.kind == FruitKind.APPLE


def test_eating_resets_fruit_age():
    game = make_service()
    state = game.state()
    state.food = Fruit(Cell(3, 5, 6), FruitKind.STAR)
    state.fruit_age_ms = 29_000
    state.snake = [Cell(2, 5, 6), Cell(1, 5, 6), Cell(0, 5, 6)]
    state.direction = Direction(1, 0, 0)
    game.tick()
    state = game.state()
    assert state.fruit_age_ms == 0
    assert state.star_steps[0] == 8
