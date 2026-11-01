from __future__ import annotations

import random

from ..models import Cell, Direction, GameState

MIN_STEP_MS = 60
MAX_STEP_MS = 400
DEFAULT_STEP_MS = 260


def _spawn_snake(n: int, head: Cell, direction: Direction) -> list[Cell]:
    """A 3-segment snake whose head is `head`, extending opposite `direction`."""
    tail = [Cell(head.x - direction.x * i, head.y - direction.y * i, head.z - direction.z * i) for i in (1, 2)]
    return [head, *tail]


class InMemoryGameService:
    """Default GameService implementation. Deterministic via injectable RNG.

    Multiplayer: mode="multi" runs two snakes on one board; each player has
    its own direction queue and score. A dead snake loses (status "dead",
    `loser` set to its index); in single mode the semantics are unchanged.
    """

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._state: GameState | None = None
        self._dir_queues: list[list[Direction]] = []

    def new_game(
        self,
        torus: bool = True,
        grid_size: int = 10,
        step_time_ms: int = DEFAULT_STEP_MS,
        mode: str = "single",
    ) -> GameState:
        n = grid_size
        mid = n // 2
        if mode == "multi":
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
        state = GameState(
            grid_size=n,
            snake=snakes[0],
            direction=directions[0],
            food=Cell(0, mid, mid + 1),
            score=scores[0],
            step_time_ms=step_time_ms,
            torus=torus,
            snakes=snakes,
            directions=directions,
            scores=scores,
            mode=mode,
        )
        state.food = self._spawn_food(state)
        self._state = state
        return state

    def state(self) -> GameState:
        if self._state is None:
            return self.new_game()
        return self._state

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

    def _drain_direction(self, state: GameState, player: int) -> None:
        if self._dir_queues[player]:
            state.directions[player] = self._dir_queues[player].pop(0)

    def step(self) -> GameState:
        state = self.state()
        if state.status != "running":
            return state
        for i in range(state.num_players):
            self._drain_direction(state, i)
        n = state.grid_size
        new_heads: list[Cell | None] = []
        dead: list[int] = []
        eating: list[bool] = []
        for i, snake in enumerate(state.snakes):
            head = snake[0]
            d = state.directions[i]
            nx, ny, nz = head.x + d.x, head.y + d.y, head.z + d.z
            if state.torus:
                nx, ny, nz = nx % n, ny % n, nz % n
            elif not (0 <= nx < n and 0 <= ny < n and 0 <= nz < n):
                new_heads.append(None)
                dead.append(i)
                eating.append(False)
                continue
            new_head = Cell(nx, ny, nz)
            is_eating = new_head == state.food
            body = snake if is_eating else snake[:-1]
            others = [c for j, s in enumerate(state.snakes) if j != i for c in s]
            if new_head in body or new_head in others:
                new_heads.append(None)
                dead.append(i)
                eating.append(False)
            else:
                new_heads.append(new_head)
                eating.append(is_eating)
        head_cells = [h for h in new_heads if h is not None]
        if len(head_cells) != len(set(head_cells)):
            # head-on collision: all involved heads die
            for i, h in enumerate(new_heads):
                if h is not None and head_cells.count(h) > 1 and i not in dead:
                    dead.append(i)
                    new_heads[i] = None
        if dead:
            state.status = "dead"
            state.loser = dead[0] if len(dead) == 1 else None
            return state
        any_eating = False
        for i, new_head in enumerate(new_heads):
            assert new_head is not None
            state.snakes[i] = [new_head, *state.snakes[i]]
            if eating[i]:
                any_eating = True
                state.scores[i] += 10
                state.step_time_ms = max(MIN_STEP_MS, state.step_time_ms - 4)
            else:
                state.snakes[i].pop()
        if any_eating:
            free = self._free_cells(state)
            if not free:
                state.status = "won"
            else:
                state.food = self._rng.choice(free)
        return state

    def set_torus(self, enabled: bool) -> GameState:
        state = self.state()
        state.torus = enabled
        return state

    def _free_cells(self, state: GameState) -> list[Cell]:
        occupied = {c for s in state.snakes for c in s}
        n = state.grid_size
        return [Cell(x, y, z) for x in range(n) for y in range(n) for z in range(n)
                if Cell(x, y, z) not in occupied]

    def _spawn_food(self, state: GameState) -> Cell:
        free = self._free_cells(state)
        return self._rng.choice(free) if free else state.food
