"""Server-side game loop: advances the game on the server's clock.

The client no longer calls /api/step; it polls /api/state and renders.
"""

from __future__ import annotations

import asyncio

from .contracts import GameService, ScoreService


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
            self._game.step()
            if self._game.state().status != "running":
                self._active = False
                self._score.submit(self._game.state().score)
            await asyncio.sleep(self._game.state().step_time_ms / 1000.0)
