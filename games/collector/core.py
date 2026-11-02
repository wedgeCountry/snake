"""Collector core: a pure 2D grid game — move, eat dots, score. Zero I/O,
injectable RNG. Implements the pipeline Game protocol."""

from __future__ import annotations

import random
from typing import Any

from ..engine import Game, GameState
from .config import CollectorConfig

_DIRS = {
    "left": (-1, 0), "right": (1, 0),
    "up": (0, 1), "down": (0, -1),
}


class CollectorState(GameState):
    state_schema_version = 1

    def __init__(self, grid_size: int, pos: tuple[int, int], dots: list[tuple[int, int]],
                 score: int, status: str = "running", step_time_ms: int = 200) -> None:
        self.grid_size = grid_size
        self.pos = pos
        self.dots = list(dots)
        self.score = score
        self.status = status
        self.step_time_ms = step_time_ms


class CollectorGame:
    def __init__(self, rng: random.Random | None = None,
                 config: CollectorConfig | None = None) -> None:
        self._rng = rng or random.Random()
        self._config = config or CollectorConfig()
        self._state: CollectorState | None = None
        self._pending: tuple[int, int] | None = None

    @property
    def state_schema_version(self) -> int:
        return CollectorState.state_schema_version

    def init(self, config: Any = None) -> CollectorState:
        cfg = config if isinstance(config, CollectorConfig) else self._config
        n = cfg.grid_size
        pos = (n // 2, n // 2)
        dots = self._spawn_dots(cfg, {pos})
        self._state = CollectorState(n, pos, dots, 0, step_time_ms=cfg.step_time_ms)
        return self._state

    def state(self) -> CollectorState:
        if self._state is None:
            return self.init()
        return self._state

    def max_players(self) -> int:
        return 1

    def is_terminal(self) -> bool:
        return self.state().status != "running"

    def apply_action(self, player: int, action: dict[str, Any]) -> None:
        name = str(action["direction"])
        if name not in _DIRS:
            raise ValueError(f"unknown direction: {name}")
        if player != 0:
            raise ValueError("collector is single-player")
        self._pending = _DIRS[name]

    def tick(self) -> CollectorState:
        state = self.state()
        if state.status != "running":
            return state
        d = self._pending or (1, 0)
        self._pending = None
        nx, ny = state.pos[0] + d[0], state.pos[1] + d[1]
        n = state.grid_size
        if not (0 <= nx < n and 0 <= ny < n):
            state.status = "dead"
            return state
        state.pos = (nx, ny)
        if state.pos in state.dots:
            state.dots.remove(state.pos)
            state.score += 10
            if not state.dots:
                state.status = "won"
            else:
                state.dots.extend(self._spawn_dots(self._config, set(state.dots) | {state.pos}))
        return state

    def _spawn_dots(self, cfg: CollectorConfig, occupied: set[tuple[int, int]]) -> list[tuple[int, int]]:
        n = cfg.grid_size
        free = [(x, y) for x in range(n) for y in range(n) if (x, y) not in occupied]
        self._rng.shuffle(free)
        return free[: cfg.dot_count]
