from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class GameState:
    """Full game state and its API serialization in one place."""

    grid_size: int
    snake: list[Cell]
    direction: Direction
    food: Cell
    score: int
    step_time_ms: int
    torus: bool
    status: str = "running"  # running | dead | won

    def snapshot(self) -> "GameState":
        return GameState(
            grid_size=self.grid_size,
            snake=list(self.snake),
            direction=self.direction,
            food=self.food,
            score=self.score,
            step_time_ms=self.step_time_ms,
            torus=self.torus,
            status=self.status,
        )

    def to_dict(self) -> dict:
        return {
            "gridSize": self.grid_size,
            "snake": [c.to_dict() for c in self.snake],
            "direction": self.direction.to_dict(),
            "food": self.food.to_dict(),
            "score": self.score,
            "stepTimeMs": self.step_time_ms,
            "torus": self.torus,
            "status": self.status,
        }
