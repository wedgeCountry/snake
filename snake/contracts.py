"""Service contracts (Protocols). All consumers depend only on these interfaces,
never on concrete implementations — the Service Contracts pattern."""

from __future__ import annotations

from typing import Protocol

from .models import Direction, GameState


class GameService(Protocol):
    """Core game logic. Pure and fully testable, no I/O."""

    def new_game(self, torus: bool = True, grid_size: int = 10) -> GameState: ...

    def state(self) -> GameState: ...

    def set_direction(self, direction: Direction) -> None: ...

    def step(self) -> GameState: ...

    def set_torus(self, enabled: bool) -> GameState: ...


class ScoreService(Protocol):
    """Persistent best-score bookkeeping."""

    def get_best(self) -> int: ...

    def submit(self, score: int) -> int: ...  # returns new best


class SettingsService(Protocol):
    """User settings (speed, torus) with persistence."""

    def get_step_time_ms(self) -> int: ...

    def set_step_time_ms(self, value: int) -> int: ...

    def get_torus(self) -> bool: ...

    def set_torus(self, enabled: bool) -> bool: ...
