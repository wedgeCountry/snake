"""Server-side game loop: advances the game on the server's clock.

The client no longer calls /api/step; it polls /api/state and renders.
"""

from __future__ import annotations

import asyncio

from .contracts import GameService, LeaderboardService, ScoreService
from .models import Direction, GameState


class GameLoop:
    def __init__(
        self,
        game: GameService,
        score: ScoreService,
        leaderboard: LeaderboardService | None = None,
        user_id: str | None = None,
        mode: str = "single",
    ) -> None:
        self._game = game
        self._score = score
        self._leaderboard = leaderboard
        self._user_id = user_id
        self._mode = mode
        self._task: asyncio.Task | None = None
        self._active = False

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def activate(self) -> None:
        self._active = True

    def state(self) -> GameState:
        return self._game.state().snapshot()

    def set_context(self, user_id: str | None, mode: str) -> None:
        """Set which user/mode the next submitted score is registered for."""
        self._user_id = user_id
        self._mode = mode

    def step(self, action: str | None = None) -> GameState:
        """Advance the game one step. An optional action (direction name)
        is queued first and applied by this step."""
        if action is not None:
            self._game.set_direction(Direction.from_name(action))
        state = self._game.step()
        if state.status != "running":
            self._active = False
            self._score.submit(state.score)
            if self._leaderboard is not None and self._user_id:
                for i, s in enumerate(state.scores):
                    player_id = self._user_id if i == 0 else f"{self._user_id}#p{i + 1}"
                    self._leaderboard.submit(player_id, self._mode, s)
        return state.snapshot()

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
        while True:
            state = self._game.state()
            if not self._active or state.status != "running":
                await asyncio.sleep(0.25)
                continue
            self.step()
            await asyncio.sleep(self._game.state().step_time_ms / 1000.0)
