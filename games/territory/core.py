"""Territory core — a pure single-player strategy game: steer a settler over a
grid, claim land next to your territory, grab gold mines for extra income, and
cover enough of the map before the turn limit. Zero I/O, injectable RNG.
Implements the pipeline Game protocol."""

from __future__ import annotations

import random
from typing import Any

from ..engine import GameState
from .config import TerritoryConfig

_DIRS = {
    "left": (-1, 0), "right": (1, 0),
    "up": (0, -1), "down": (0, 1),
    "forward": (0, 1), "back": (0, -1),
}


class TerritoryState(GameState):
    state_schema_version = 1

    def __init__(self, grid_size: int, pos: tuple[int, int],
                 territory: set[tuple[int, int]], mines: set[tuple[int, int]],
                 gold: int, score: int, turn: int, max_turns: int, goal: int,
                 status: str = "running", step_time_ms: int = 300) -> None:
        self.grid_size = grid_size
        self.pos = pos
        self.territory = set(territory)
        self.mines = set(mines)
        self.gold = gold
        self.score = score
        self.turn = turn
        self.max_turns = max_turns
        self.goal = goal
        self.status = status
        self.step_time_ms = step_time_ms


class TerritoryGame:
    def __init__(self, rng: random.Random | None = None,
                 config: TerritoryConfig | None = None) -> None:
        self._rng = rng or random.Random()
        self._config = config or TerritoryConfig()
        self._state: TerritoryState | None = None
        self._pending: tuple[int, int] | None = None

    @property
    def state_schema_version(self) -> int:
        return TerritoryState.state_schema_version

    def init(self, config: Any = None) -> TerritoryState:
        if isinstance(config, TerritoryConfig):
            cfg = config
        else:
            step = getattr(config, "step_time_ms", None)
            cfg = TerritoryConfig(step_time_ms=step) if isinstance(step, int) else self._config
        n = cfg.grid_size
        center = (n // 2, n // 2)
        free = [(x, y) for x in range(n) for y in range(n) if (x, y) != center]
        self._rng.shuffle(free)
        mines = set(free[: cfg.mine_count])
        self._state = TerritoryState(n, center, {center}, mines, 0, 0, 0,
                                     cfg.max_turns, cfg.territory_goal,
                                     step_time_ms=cfg.step_time_ms)
        self._config = cfg
        self._pending = None
        return self._state

    def state(self) -> TerritoryState:
        if self._state is None:
            return self.init()
        return self._state

    def max_players(self) -> int:
        return 1

    def is_terminal(self) -> bool:
        return self.state().status != "running"

    def apply_action(self, player: int, action: dict[str, Any]) -> None:
        if player != 0:
            raise ValueError("territory is single-player")
        name = str(action["direction"])
        if name not in _DIRS:
            raise ValueError(f"unknown direction: {name}")
        self._pending = _DIRS[name]

    def tick(self) -> TerritoryState:
        state = self.state()
        if state.status != "running":
            return state
        cfg = self._config
        state.turn += 1
        n = state.grid_size
        d = self._pending or (1, 0)
        self._pending = None
        nx = min(max(state.pos[0] + d[0], 0), n - 1)
        ny = min(max(state.pos[1] + d[1], 0), n - 1)
        state.pos = (nx, ny)
        # claiming by the settler only works on a free cell next to the territory
        if (nx, ny) not in state.territory and self._adjacent(state.territory, (nx, ny), n):
            state.territory.add((nx, ny))
        # the realm also grows on its own: one random frontier cell per turn
        frontier = self._frontier(state, n)
        if frontier:
            state.territory.add(self._rng.choice(frontier))
        # income: one gold per territory cell, plus a bonus per claimed mine
        state.gold += len(state.territory) + cfg.mine_bonus * len(state.territory & state.mines)
        state.score = state.gold + cfg.score_per_cell * len(state.territory)
        free = self._free_cells(state, n)
        if not free or state.turn >= state.max_turns:
            state.status = "won" if (not free or len(state.territory) >= state.goal) else "dead"
        return state

    def _adjacent(self, territory: set[tuple[int, int]], cell: tuple[int, int], n: int) -> bool:
        x, y = cell
        return any((x + dx, y + dy) in territory
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                   if 0 <= x + dx < n and 0 <= y + dy < n)

    def _frontier(self, state: TerritoryState, n: int) -> list[tuple[int, int]]:
        frontier: set[tuple[int, int]] = set()
        for (x, y) in state.territory:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c = (x + dx, y + dy)
                if 0 <= c[0] < n and 0 <= c[1] < n and c not in state.territory:
                    frontier.add(c)
        return sorted(frontier)

    def _free_cells(self, state: TerritoryState, n: int) -> list[tuple[int, int]]:
        return [(x, y) for x in range(n) for y in range(n) if (x, y) not in state.territory]
