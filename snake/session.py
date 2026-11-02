"""Session-scoped game instances: one Game per session, idle expiry, and the
per-session asyncio loop. No global mutable game state lives on app.state.

One authoritative stepper per session: the SessionLoop's background task is
the only thing that ticks a session's game. Transports (REST/WS) only push
or accept actions.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Callable

from games.engine import Game
from games.registry import get as get_game_info
from .contracts import GameSession

IDLE_TTL_S = 30 * 60


class InMemorySessionService:
    """In-memory SessionService with idle expiry. The interface allows a
    shared (e.g. DB-backed) store later; a live session owns an asyncio task,
    so a shared store would need a loop claim/lease strategy."""

    def __init__(self, ttl_s: float = IDLE_TTL_S, now: Callable[[], float] = time.monotonic,
                 on_expire: Callable[[str], None] | None = None) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._ttl_s = ttl_s
        self._now = now
        self._on_expire = on_expire

    def create(self, game_id: str, user_id: str, mode: str) -> str:
        info = get_game_info(game_id)
        session_id = secrets.token_hex(16)
        game: Game = info.factory(None)
        now = self._now()
        session = GameSession(session_id, game_id, game, user_id, mode)
        session.created_at = now
        session.last_active = now
        self._sessions[session_id] = session
        return session_id

    def get(self, session_id: str) -> GameSession | None:
        self._expire()
        return self._sessions.get(session_id)

    def touch(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.last_active = self._now()

    def drop(self, session_id: str) -> None:
        if self._sessions.pop(session_id, None) is not None and self._on_expire is not None:
            self._on_expire(session_id)

    def _expire(self) -> None:
        now = self._now()
        expired = [sid for sid, s in self._sessions.items() if now - s.last_active > self._ttl_s]
        for sid in expired:
            self.drop(sid)


class SessionLoop:
    """One authoritative stepper per session: an asyncio task ticking the
    session's game on the server clock. Score submission happens here, once,
    when the game reaches a terminal state. The task ends itself on terminal
    state so no loop outlives its session."""

    def __init__(self, session: GameSession, score_service, leaderboard_service=None,
                 on_terminal: Callable[[GameSession], None] | None = None,
                 on_finished: Callable[[], None] | None = None) -> None:
        self._session = session
        self._score = score_service
        self._leaderboard = leaderboard_service
        self._on_terminal = on_terminal
        self._on_finished = on_finished
        self._task: asyncio.Task | None = None
        self._submitted = False

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def step(self, action: dict | None = None) -> None:
        """Advance the game one tick. Called only by the loop's own task or by
        tests — never concurrently with it."""
        game = self._session.game
        if action is not None:
            game.apply_action(int(action.get("player", 0)), action)
        state = game.tick()
        if game.is_terminal() and not self._submitted:
            self._submitted = True
            scores = getattr(state, "scores", None) or [getattr(state, "score", 0)]
            self._score.submit(self._session.game_id, scores[0])
            if self._leaderboard is not None:
                for i, s in enumerate(scores):
                    player_id = self._session.user_id if i == 0 else f"{self._session.user_id}#p{i + 1}"
                    self._leaderboard.submit(player_id, self._session.game_id, self._session.mode, s)
            if self._on_terminal is not None:
                self._on_terminal(self._session)

    async def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        cancelled = False
        try:
            while not self._session.game.is_terminal():
                self.step()
                step_ms = getattr(self._session.game.state(), "step_time_ms", 260)
                await asyncio.sleep(step_ms / 1000.0)
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            self._task = None
            # only natural termination (game over) drops the loop; a manual
            # stop() keeps it registered so tests/tools can step directly
            if not cancelled and self._on_finished is not None:
                self._on_finished()
