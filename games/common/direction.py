"""Shared direction model and input queue for grid-based games.

`Direction` is a 3D unit vector; 2D games use the XZ plane via
`Direction.from_name_2d` + `as_2d()`. `DirectionQueue` is the standard
one-deep-per-tick input buffer: rejects no-ops and 180-degree turns.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Direction:
    x: int
    y: int
    z: int

    @classmethod
    def from_name(cls, name: str) -> "Direction":
        """3D names: up/down are the vertical (Y) axis, forward/back are Z."""
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

    @classmethod
    def from_name_2d(cls, name: str) -> "Direction":
        """2D names on the XZ plane: up = -Z (screen up), down/forward = +Z."""
        mapping = {
            "left": cls(-1, 0, 0),
            "right": cls(1, 0, 0),
            "up": cls(0, 0, -1),
            "down": cls(0, 0, 1),
            "forward": cls(0, 0, 1),
            "back": cls(0, 0, -1),
        }
        if name not in mapping:
            raise ValueError(f"unknown direction: {name}")
        return mapping[name]

    def is_opposite(self, other: "Direction") -> bool:
        return (self.x, self.y, self.z) == (-other.x, -other.y, -other.z)

    def as_2d(self) -> tuple[int, int]:
        """XZ-plane projection as an (dx, dz) pair for 2D grid games."""
        return (self.x, self.z)


class DirectionQueue:
    """Buffered direction input: one direction applied per tick, rejecting
    repeats and 180-degree turns relative to the last queued/current one."""

    def __init__(self, max_depth: int = 4) -> None:
        self._queue: list[Direction] = []
        self.max_depth = max_depth

    def push(self, direction: Direction, last: Direction) -> bool:
        if direction == last or direction.is_opposite(last):
            return False
        if len(self._queue) >= self.max_depth:
            return False
        self._queue.append(direction)
        return True

    def pop(self) -> Direction | None:
        return self._queue.pop(0) if self._queue else None

    def peek_last(self) -> Direction | None:
        return self._queue[-1] if self._queue else None

    def clear(self) -> None:
        self._queue.clear()

    def __len__(self) -> int:
        return len(self._queue)
