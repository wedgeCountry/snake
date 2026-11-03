"""Collector game entry: registers "collector" in the game registry."""

from __future__ import annotations

import random

from ..engine import Game
from ..registry import register
from .core import CollectorGame, CollectorState


def _factory(rng: random.Random | None) -> Game:
    return CollectorGame(rng=rng)


def _serialize(state) -> dict:
    st = state if isinstance(state, CollectorState) else None
    return {"pos": list(st.pos), "dots": [list(d) for d in st.dots],
            "score": st.score, "gridSize": st.grid_size,
            "stepTimeMs": st.step_time_ms} if st else {}


register("collector", name="Collector", real_time=True, max_players=1,
         factory=_factory, serialize=_serialize)
