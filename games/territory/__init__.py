"""Territory game entry: registers "territory" (single-player strategy)."""

from __future__ import annotations

import random

from ..engine import Game
from ..registry import register
from .core import TerritoryGame, TerritoryState


def _factory(rng: random.Random | None) -> Game:
    return TerritoryGame(rng=rng)


def _serialize(state) -> dict:
    if not isinstance(state, TerritoryState):
        return {}
    return {
        "gridSize": state.grid_size,
        "pos": list(state.pos),
        "territory": [list(c) for c in sorted(state.territory)],
        "mines": [list(c) for c in sorted(state.mines)],
        "gold": state.gold,
        "score": state.score,
        "turn": state.turn,
        "maxTurns": state.max_turns,
        "goal": state.goal,
        "status": state.status,
        "stepTimeMs": state.step_time_ms,
    }


register("territory", name="Territory", real_time=True, max_players=1,
         factory=_factory, serialize=_serialize)
