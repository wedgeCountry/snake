"""Snake effect handlers, registered per fruit kind through the generic
Effects registry (the pipeline-level pattern from games/engine.py)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..engine import Effects
from .config import GRID_RESIZE_STEP, MAX_GRID_SIZE, MIN_GRID_SIZE
from .models import Cell, Direction, Fruit, FruitKind

if TYPE_CHECKING:
    from .core import SnakeGame


def build_effects() -> Effects:
    effects = Effects()
    effects.register(FruitKind.APPLE.value, _apple)
    effects.register(FruitKind.REVERSE.value, _reverse)
    effects.register(FruitKind.GROW_GRID.value, lambda s, p, g: _resize(g, s, p, GRID_RESIZE_STEP))
    effects.register(FruitKind.SHRINK_GRID.value, lambda s, p, g: _resize(g, s, p, -GRID_RESIZE_STEP))
    effects.register(FruitKind.STAR.value, _star)
    return effects


def _apple(state, player: int, game: "SnakeGame") -> None:
    from .config import MIN_STEP_MS
    state.scores[player] += 10
    state.step_time_ms = max(MIN_STEP_MS, state.step_time_ms - 4)


def _reverse(state, player: int, game: "SnakeGame") -> None:
    state.scores[player] += 5
    d = state.directions[player]
    state.directions[player] = Direction(-d.x, -d.y, -d.z)
    state.snakes[player].reverse()  # head/tail swap: safe 180-degree turn
    game.clear_queue(player)


def _resize(game: "SnakeGame", state, player: int, delta: int) -> None:
    from .config import MAX_GRID_SIZE, MIN_GRID_SIZE
    state.scores[player] += 5
    new_n = min(MAX_GRID_SIZE, max(MIN_GRID_SIZE, state.grid_size + delta))
    if new_n == state.grid_size:
        return
    for snake in state.snakes:
        snake[:] = [Cell(min(c.x, new_n - 1), min(c.y, new_n - 1), min(c.z, new_n - 1)) for c in snake]
    if state.food.cell.x < new_n and state.food.cell.y < new_n and state.food.cell.z < new_n:
        pass
    else:
        state.food = Fruit(game.rng.choice(game.free_cells(state)), state.food.kind)
    state.grid_size = new_n
    state.food = Fruit(Cell(state.food.cell.x % new_n, state.food.cell.y % new_n, state.food.cell.z % new_n), state.food.kind)


def _star(state, player: int, game: "SnakeGame") -> None:
    state.scores[player] += 15
    state.star_steps[player] = game.config.star_steps
