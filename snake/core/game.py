from __future__ import annotations

import random

from ..models import Cell, Direction, GameState

MIN_STEP_MS = 60
MAX_STEP_MS = 400
DEFAULT_STEP_MS = 260


class InMemoryGameService:
    """Default GameService implementation. Deterministic via injectable RNG."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._state: GameState | None = None
        self._dir_queue: list[Direction] = []

    def new_game(self, torus: bool = True, grid_size: int = 10, step_time_ms: int = DEFAULT_STEP_MS) -> GameState:
        n = grid_size
        mid = n // 2
        snake = [Cell(3, mid, mid + 1), Cell(2, mid, mid + 1), Cell(1, mid, mid + 1)]
        self._dir_queue = []
        state = GameState(
            grid_size=n,
            snake=snake,
            direction=Direction(1, 0, 0),
            food=Cell(0, mid, mid + 1),
            score=0,
            step_time_ms=step_time_ms,
            torus=torus,
        )
        state.food = self._spawn_food(state)
        self._state = state
        return state

    def state(self) -> GameState:
        if self._state is None:
            return self.new_game()
        return self._state

    def set_direction(self, direction: Direction) -> None:
        state = self.state()
        last = self._dir_queue[-1] if self._dir_queue else state.direction
        if direction == last or direction.is_opposite(last):
            return
        if len(self._dir_queue) < 4:
            self._dir_queue.append(direction)

    def _drain_direction(self, state: GameState) -> None:
        if self._dir_queue:
            state.direction = self._dir_queue.pop(0)

    def step(self) -> GameState:
        state = self.state()
        if state.status != "running":
            return state
        self._drain_direction(state)
        n = state.grid_size
        head = state.snake[0]
        d = state.direction
        nx, ny, nz = head.x + d.x, head.y + d.y, head.z + d.z
        if state.torus:
            nx, ny, nz = nx % n, ny % n, nz % n
        elif not (0 <= nx < n and 0 <= ny < n and 0 <= nz < n):
            state.status = "dead"
            return state
        new_head = Cell(nx, ny, nz)
        eating = new_head == state.food
        body = state.snake if eating else state.snake[:-1]
        if new_head in body:
            state.status = "dead"
            return state
        state.snake = [new_head, *state.snake]
        if eating:
            state.score += 10
            state.step_time_ms = max(MIN_STEP_MS, state.step_time_ms - 4)
            free = self._free_cells(state)
            if not free:
                state.status = "won"
            else:
                state.food = self._rng.choice(free)
        else:
            state.snake.pop()
        return state

    def set_torus(self, enabled: bool) -> GameState:
        state = self.state()
        state.torus = enabled
        return state

    def _free_cells(self, state: GameState) -> list[Cell]:
        occupied = set(state.snake)
        n = state.grid_size
        return [Cell(x, y, z) for x in range(n) for y in range(n) for z in range(n)
                if Cell(x, y, z) not in occupied]

    def _spawn_food(self, state: GameState) -> Cell:
        free = self._free_cells(state)
        return self._rng.choice(free) if free else state.food
