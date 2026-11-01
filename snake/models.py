from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Axis(str, Enum):
    X = "x"
    Y = "y"
    Z = "z"


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
        food: Cell,
        score: int,
        step_time_ms: int,
        torus: bool,
        status: str = "running",  # running | dead | won
        snakes: list[list[Cell]] | None = None,
        directions: list[Direction] | None = None,
        scores: list[int] | None = None,
        mode: str = "single",  # single | multi
        loser: int | None = None,  # player index that died, in multi mode
    ) -> None:
        self.grid_size = grid_size
        self.food = food
        self.step_time_ms = step_time_ms
        self.torus = torus
        self.status = status
        self.snakes = [list(s) for s in snakes] if snakes is not None else [list(snake)]
        self.directions = list(directions) if directions is not None else [direction]
        self.scores = list(scores) if scores is not None else [score]
        self.mode = mode
        self.loser = loser

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
        }
