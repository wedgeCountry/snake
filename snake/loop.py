"""Server-side game loop: advances the game on the server's clock.

The client no longer calls /api/step; it polls /api/state and renders.
"""

from __future__ import annotations

import asyncio

from .contracts import GameService, ScoreService
from .models import APIGameState, Direction


class GameLoop:
    def __init__(self, game: GameService, score: ScoreService) -> None:
        self._game = game
        self._score = score
        self._task: asyncio.Task | None = None
        self._active = False

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def activate(self) -> None:
        self._active = True

    def state(self) -> APIGameState:
        return APIGameState.from_state(self._game.state())

    def step(self, action: str | None = None) -> APIGameState:
        """Advance the game one step. An optional action (direction name)
        is queued first and applied by this step."""
        if action is not None:
            self._game.set_direction(Direction.from_name(action))
        state = self._game.step()
        if state.status != "running":
            self._active = False
            self._score.submit(state.score)
        return APIGameState.from_state(state)

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
