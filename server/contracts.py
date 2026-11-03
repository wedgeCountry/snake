"""Pipeline-wide service contracts (Protocols). All consumers depend only on
these interfaces, never on concrete implementations — the Service Contracts
pattern. Concrete impls are swappable without touching consumers."""

from __future__ import annotations

from typing import Any, Protocol

from games.engine import Action, Game, GameState

ENVELOPE_VERSION = 1

SESSION_COOKIE = "game_session"


class SessionService(Protocol):
    """Session-scoped game instances, keyed by session id. The interface is
    shaped for a future shared store with a loop claim/lease strategy."""

    def create(self, game_id: str, user_id: str, mode: str) -> str: ...

    def get(self, session_id: str) -> "GameSession | None": ...

    def touch(self, session_id: str) -> None: ...

    def drop(self, session_id: str) -> None: ...


class GameSession:
    """One game instance + its context, owned by exactly one session."""

    def __init__(self, session_id: str, game_id: str, game: Game,
                 user_id: str, mode: str) -> None:
        self.session_id = session_id
        self.game_id = game_id
        self.game = game
        self.user_id = user_id
        self.mode = mode
        self.created_at: float = 0.0
        self.last_active: float = 0.0


class ScoreService(Protocol):
    """Persistent best-score bookkeeping, keyed by game_id."""

    def get_best(self, game_id: str) -> int: ...

    def submit(self, game_id: str, score: int) -> int: ...  # returns new best


class UserService(Protocol):
    """Cookie-based user identity: each browser gets a unique ID."""

    @property
    def cookie_name(self) -> str: ...

    def new_id(self) -> str: ...

    def resolve(self, cookie_value: str | None) -> str: ...


class LeaderboardService(Protocol):
    """Per-user maximum scores per game, keyed by game_id."""

    def submit(self, user_id: str, game_id: str, mode: str, score: int) -> int: ...

    def get_best(self, user_id: str, game_id: str, mode: str) -> int: ...

    def top(self, game_id: str, mode: str, limit: int = 10) -> list[dict]: ...

    def bests(self, user_id: str) -> dict: ...  # {game_id: {mode: best}}


class SettingsService(Protocol):
    """Per-user settings keyed by user_id, with an anonymous default."""

    def get(self, user_id: str) -> dict: ...

    def set(self, user_id: str, settings: dict) -> dict: ...

    def get_step_time_ms(self, user_id: str) -> int: ...

    def get_torus(self, user_id: str) -> bool: ...


class Transport(Protocol):
    """Real-time seam behind the API layer: poll() vs subscribe()."""

    async def poll(self, session_id: str) -> dict: ...

    async def subscribe(self, session_id: str): ...  # async iterator of envelopes


def envelope(game_id: str, session: GameSession, state: GameState,
             players: list[str], status: str, meta: dict[str, Any] | None = None) -> dict:
    """Versioned wire envelope: {v, gameId, sessionId, status, players, state, meta}."""
    return {
        "v": ENVELOPE_VERSION,
        "gameId": game_id,
        "sessionId": session.session_id,
        "status": status,
        "players": players,
        "state": state,
        "meta": meta or {},
    }
