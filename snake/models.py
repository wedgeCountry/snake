from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Axis(str, Enum):
    X = "x"
    Y = "y"
    Z = "z"


class FruitKind(str, Enum):
    APPLE = "apple"              # classic: grow + score
    REVERSE = "reverse"          # revert direction (safe 180-degree turn)
    GROW_GRID = "grow_grid"      # expand the grid by 2 per axis
    SHRINK_GRID = "shrink_grid"  # shrink the grid by 2 per axis
    STAR = "star"                # indestructible for a while (can pass through itself)


@dataclass(frozen=True)
class Direction:
    x: int
    y: int
    z: int

    @classmethod
    def from_name(cls, name: str) -> "Direction":
        mapping = {
            "left": cls(-1, 0, 0),
            "right": cls(1, 0, 0),
            "up": cls(0, 1, 0),
            "down": cls(0, -1, 0),
            "forward": cls(0, 0, 1),
            "back": cls(0, 0, -1),
        }
        if name not in mapping:
            raise ValueError(f"unknown direction: {name}")
        return mapping[name]

    def is_opposite(self, other: "Direction") -> bool:
        return (self.x, self.y, self.z) == (-other.x, -other.y, -other.z)

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass(frozen=True)
class Cell:
    x: int
    y: int
    z: int

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass(frozen=True)
class Fruit:
    cell: Cell
    kind: FruitKind = FruitKind.APPLE

    @property
    def x(self) -> int:
        return self.cell.x

    @property
    def y(self) -> int:
        return self.cell.y

    @property
    def z(self) -> int:
        return self.cell.z

    def to_dict(self) -> dict:
        d = self.cell.to_dict()
        d["kind"] = self.kind.value
        return d


class GameState:
    """Full game state and its API serialization in one place.

    Multiplayer: `snakes` holds one snake per player. `snake`, `direction`
    and `score` are player-0 accessors (properties over the lists), so
    single-player code keeps working unchanged.
    """

    def __init__(
        self,
        grid_size: int,
        snake: list[Cell],
        direction: Direction,
        food: Fruit | Cell,
        score: int,
        step_time_ms: int,
        torus: bool,
        status: str = "running",  # running | dead | won
        snakes: list[list[Cell]] | None = None,
        directions: list[Direction] | None = None,
        scores: list[int] | None = None,
        mode: str = "single",  # single | multi
        loser: int | None = None,  # player index that died, in multi mode
        star_steps: list[int] | None = None,  # remaining indestructible steps per player
    ) -> None:
        self.grid_size = grid_size
        self.food = food  # property: coerces Cell into Fruit
        self.step_time_ms = step_time_ms
        self.torus = torus
        self.status = status
        self.snakes = [list(s) for s in snakes] if snakes is not None else [list(snake)]
        self.directions = list(directions) if directions is not None else [direction]
        self.scores = list(scores) if scores is not None else [score]
        self.mode = mode
        self.loser = loser
        self.star_steps = list(star_steps) if star_steps is not None else [0] * len(self.snakes)

    @property
    def food(self) -> Fruit:
        return self._food

    @food.setter
    def food(self, value: Fruit | Cell) -> None:
        self._food = value if isinstance(value, Fruit) else Fruit(value)

    @property
    def food_kind(self) -> FruitKind:
        return self.food.kind

    @property
    def snake(self) -> list[Cell]:
        return self.snakes[0]

    @snake.setter
    def snake(self, value: list[Cell]) -> None:
        self.snakes[0] = list(value)

    @property
    def direction(self) -> Direction:
        return self.directions[0]

    @direction.setter
    def direction(self, value: Direction) -> None:
        self.directions[0] = value

    @property
    def score(self) -> int:
        return self.scores[0]

    @score.setter
    def score(self, value: int) -> None:
        self.scores[0] = value

    @property
    def num_players(self) -> int:
        return len(self.snakes)

    def snapshot(self) -> "GameState":
        return GameState(
            grid_size=self.grid_size,
            snake=self.snake,
            direction=self.direction,
            food=self.food,
            score=self.score,
            step_time_ms=self.step_time_ms,
            torus=self.torus,
            status=self.status,
            snakes=self.snakes,
            directions=self.directions,
            scores=self.scores,
            mode=self.mode,
            loser=self.loser,
            star_steps=self.star_steps,
        )

    def to_dict(self) -> dict:
        return {
            "gridSize": self.grid_size,
            "snake": [c.to_dict() for c in self.snake],
            "snakes": [[c.to_dict() for c in s] for s in self.snakes],
            "direction": self.direction.to_dict(),
            "directions": [d.to_dict() for d in self.directions],
            "food": self.food.to_dict(),
            "score": self.score,
            "scores": list(self.scores),
            "stepTimeMs": self.step_time_ms,
            "torus": self.torus,
            "status": self.status,
            "mode": self.mode,
            "loser": self.loser,
            "starSteps": list(self.star_steps),
        }


class GameSinglePlayerState(GameState):
    """Single-player view over a (possibly multiplayer) GameState.

    Wraps an existing state and exposes only player 0's snake, direction
    and score, with mode pinned to "single". Intended for tests that want
    to assert single-player semantics on any game state.
    """

    def __init__(self, state: GameState) -> None:
        super().__init__(
            grid_size=state.grid_size,
            snake=state.snakes[0],
            direction=state.directions[0],
            food=state.food,
            score=state.scores[0],
            step_time_ms=state.step_time_ms,
            torus=state.torus,
            status=state.status,
            mode="single",
        )
