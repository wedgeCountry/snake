"""Snake core: pure game logic implementing the pipeline `Game` protocol.

Zero I/O, injectable RNG, fully testable with pytest.
"""

from __future__ import annotations

import random
from typing import Any

from ..common.board import free_cells, weighted_choice
from ..engine import Game, GameState
from .config import (
    DEFAULT_STEP_MS,
    MAX_GRID_SIZE,
    MIN_GRID_SIZE,
    SnakeConfig,
)
from .effects import build_effects
from .models import Cell, Direction, Fruit, FruitKind, SnakeState


def _spawn_snake(n: int, head: Cell, direction: Direction) -> list[Cell]:
    """A 3-segment snake whose head is `head`, extending opposite `direction`."""
    tail = [Cell(head.x - direction.x * i, head.y - direction.y * i, head.z - direction.z * i) for i in (1, 2)]
    return [head, *tail]


class SnakeGame:
    """One snake game instance. Multiplayer: mode="multi" runs two snakes on
    one board; a dead snake loses (status "dead", `loser` set to its index)."""

    def __init__(self, rng: random.Random | None = None, config: SnakeConfig | None = None) -> None:
        self._rng = rng or random.Random()
        self._config = config or SnakeConfig()
        self._effects = build_effects()
        self._state: SnakeState | None = None
        self._dir_queues: list[list[Direction]] = []

    @property
    def rng(self) -> random.Random:
        return self._rng

    @property
    def config(self) -> SnakeConfig:
        return self._config

    @property
    def state_schema_version(self) -> int:
        return SnakeState.state_schema_version

    def init(self, config: Any = None) -> GameState:
        cfg = config if isinstance(config, SnakeConfig) else self._config
        n = cfg.grid_size
        mid = n // 2
        if cfg.mode == "multi":
            snakes = [
                _spawn_snake(n, Cell(2, mid, mid), Direction(1, 0, 0)),
                _spawn_snake(n, Cell(n - 3, mid, mid), Direction(-1, 0, 0)),
            ]
            directions = [Direction(1, 0, 0), Direction(-1, 0, 0)]
            scores = [0, 0]
        else:
            snakes = [_spawn_snake(n, Cell(3, mid, mid + 1), Direction(1, 0, 0))]
            directions = [Direction(1, 0, 0)]
            scores = [0]
        self._dir_queues = [[] for _ in snakes]
        state = SnakeState(
            grid_size=n,
            snake=snakes[0],
            direction=directions[0],
            food=Cell(0, mid, mid + 1),
            score=scores[0],
            step_time_ms=cfg.step_time_ms,
            torus=cfg.torus,
            snakes=snakes,
            directions=directions,
            scores=scores,
            mode=cfg.mode,
        )
        state.food = self._spawn_fruit(state)
        self._state = state
        self._config = cfg
        return state

    def state(self) -> SnakeState:
        if self._state is None:
            return self.init()
        return self._state

    def max_players(self) -> int:
        return 2

    def is_terminal(self) -> bool:
        return self.state().status != "running"

    def apply_action(self, player: int, action: dict[str, Any]) -> None:
        direction = Direction.from_name(str(action["direction"]))
        self.set_direction(direction, player=player)

    def set_direction(self, direction: Direction, player: int = 0) -> None:
        state = self.state()
        if not (0 <= player < state.num_players):
            return
        queue = self._dir_queues[player]
        last = queue[-1] if queue else state.directions[player]
        if direction == last or direction.is_opposite(last):
            return
        if len(queue) < 4:
            queue.append(direction)

    def clear_queue(self, player: int) -> None:
        if 0 <= player < len(self._dir_queues):
            self._dir_queues[player].clear()

    def tick(self) -> SnakeState:
        state = self.state()
        if state.status != "running":
            return state
        for i in range(state.num_players):
            self._drain_direction(state, i)
            if state.star_steps[i] > 0:
                state.star_steps[i] -= 1
        n = state.grid_size
        new_heads: list[Cell | None] = []
        dead: list[int] = []
        eaten: list[FruitKind | None] = []
        for i, snake in enumerate(state.snakes):
            head = snake[0]
            d = state.directions[i]
            nx, ny, nz = head.x + d.x, head.y + d.y, head.z + d.z
            if state.torus:
                nx, ny, nz = nx % n, ny % n, nz % n
            elif not (0 <= nx < n and 0 <= ny < n and 0 <= nz < n):
                new_heads.append(None)
                dead.append(i)
                eaten.append(None)
                continue
            new_head = Cell(nx, ny, nz)
            is_eating = new_head == state.food.cell
            starred = state.star_steps[i] > 0
            body = snake if (is_eating or starred) else snake[:-1]
            others = [c for j, s in enumerate(state.snakes) if j != i for c in s]
            if (new_head in body or new_head in others) and not starred:
                new_heads.append(None)
                dead.append(i)
                eaten.append(None)
            else:
                new_heads.append(new_head)
                eaten.append(state.food.kind if is_eating else None)
        head_cells = [h for h in new_heads if h is not None]
        if len(head_cells) != len(set(head_cells)):
            # head-on collision: all involved heads die unless starred
            for i, h in enumerate(new_heads):
                if h is not None and head_cells.count(h) > 1 and i not in dead and state.star_steps[i] <= 0:
                    dead.append(i)
                    new_heads[i] = None
        if dead:
            state.status = "dead"
            state.loser = dead[0] if len(dead) == 1 else None
            return state
        self._age_fruit(state)
        any_eating = False
        for i, new_head in enumerate(new_heads):
            assert new_head is not None
            kind = eaten[i]
            state.snakes[i] = [new_head, *state.snakes[i]]
            if kind is not None:
                any_eating = True
                self._effects.handle(kind.value, state, i, self)
            else:
                state.snakes[i].pop()
        if any_eating:
            free = self.free_cells(state)
            if not free:
                state.status = "won"
            else:
                state.food = self._spawn_fruit(state)
                state.fruit_age_ms = 0
        return state

    def _drain_direction(self, state: SnakeState, player: int) -> None:
        if self._dir_queues[player]:
            state.directions[player] = self._dir_queues[player].pop(0)

    def _age_fruit(self, state: SnakeState) -> None:
        """Timed fruit kinds despawn after their duration and respawn."""
        duration_s = self._config.fruit_durations_s.get(state.food.kind)
        if duration_s is None:
            return
        state.fruit_age_ms += state.step_time_ms
        if state.fruit_age_ms < duration_s * 1000:
            return
        free = self.free_cells(state)
        if free:
            state.food = self._spawn_fruit(state)
            state.fruit_age_ms = 0

    def set_torus(self, enabled: bool) -> SnakeState:
        state = self.state()
        state.torus = enabled
        return state

    def free_cells(self, state: SnakeState) -> list[Cell]:
        occupied = {c for s in state.snakes for c in s}
        occupied.add(state.food.cell)
        n = state.grid_size
        return [Cell(x, y, z) for x, y, z in free_cells(n, occupied)]

    def _spawn_fruit(self, state: SnakeState) -> Fruit:
        free = self.free_cells(state)
        if not free:
            return state.food
        cell = self._rng.choice(free)
        kind = FruitKind(weighted_choice(self._rng, [(k.value, w) for k, w in self._config.fruit_weights]))
        return Fruit(cell, kind)
