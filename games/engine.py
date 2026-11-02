"""Pipeline-wide game contracts.

Every game implements the `Game` protocol. Consumers (routes, loops,
sessions, views) depend only on these protocols, never on concrete games.
Game cores contain zero I/O and take an injectable RNG.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

Action = dict[str, Any]


class GameState:
    """Base class for game states. Serialization lives in DTO classes
    (see the `Serializable` protocol), never on the domain model."""

    state_schema_version: int = 1


class Serializable(Protocol):
    """DTO classes implement this; domain models do not."""

    def to_dict(self) -> dict: ...


@runtime_checkable
class Game(Protocol):
    """One game instance per session. The server is the only stepper:
    clients submit actions, the server owns all state transitions."""

    def init(self, config: Any) -> GameState: ...

    def state(self) -> GameState: ...

    def apply_action(self, player: int, action: Action) -> None: ...

    def tick(self) -> GameState: ...

    def max_players(self) -> int: ...

    def is_terminal(self) -> bool: ...

    @property
    def state_schema_version(self) -> int: ...


@dataclass
class GameInfo:
    id: str
    name: str
    real_time: bool
    max_players: int
    factory: Callable[[random.Random | None], Game] = field(repr=False)


@dataclass(frozen=True)
class RuleConfig:
    """Base for per-game rule configuration: effect weights and durations."""

    weights: dict[str, int] = field(default_factory=dict)
    durations_s: dict[str, float | None] = field(default_factory=dict)


class Effects:
    """Generic effect registry: games register handlers per effect kind and
    declare weights/durations in their config dataclass. This is the
    pipeline-level pattern, not snake-specific."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[GameState, int, Any], None]] = {}

    def register(self, kind: str, handler: Callable[[GameState, int, Any], None]) -> None:
        self._handlers[kind] = handler

    def handle(self, kind: str, state: GameState, player: int, ctx: Any = None) -> None:
        handler = self._handlers.get(kind)
        if handler is not None:
            handler(state, player, ctx)

    def kinds(self) -> list[str]:
        return list(self._handlers)
