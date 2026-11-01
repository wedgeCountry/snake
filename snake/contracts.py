"""Service contracts (Protocols). All consumers depend only on these interfaces,
never on concrete implementations — the Service Contracts pattern."""

from __future__ import annotations

from typing import Protocol

from .core.game import DEFAULT_STEP_MS
from .models import Direction, GameState


class GameService(Protocol):
    """Core game logic. Pure and fully testable, no I/O."""

    def new_game(self, torus: bool = True, grid_size: int = 10, step_time_ms: int = DEFAULT_STEP_MS) -> GameState: ...

    def state(self) -> GameState: ...

    def set_direction(self, direction: Direction) -> None: ...

    def step(self) -> GameState: ...

    def set_torus(self, enabled: bool) -> GameState: ...


class ScoreService(Protocol):
    """Persistent best-score bookkeeping."""

    def get_best(self) -> int: ...

    def submit(self, score: int) -> int: ...  # returns new best


class UserService(Protocol):
    """Cookie-based user identity: each browser gets a unique ID."""

    @property
    def cookie_name(self) -> str: ...

    def new_id(self) -> str: ...

    def resolve(self, cookie_value: str | None) -> str: ...


class LeaderboardService(Protocol):
    """Per-user maximum scores on the single-play and multiplayer boards."""

    def submit(self, user_id: str, mode: str, score: int) -> int: ...  # returns user's max

    def get_best(self, user_id: str, mode: str) -> int: ...

    def top(self, mode: str, limit: int = 10) -> list[dict]: ...


class SettingsService(Protocol):
    """User settings (speed, torus) with persistence."""

    def get_step_time_ms(self) -> int: ...

    def set_step_time_ms(self, value: int) -> int: ...

    def get_torus(self) -> bool: ...

    def set_torus(self, enabled: bool) -> bool: ...
