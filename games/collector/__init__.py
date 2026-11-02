"""Collector game entry: registers "collector" in the game registry."""

from __future__ import annotations

import random

from ..engine import Game
from ..registry import register
from .core import CollectorGame


def _factory(rng: random.Random | None) -> Game:
    return CollectorGame(rng=rng)


register("collector", name="Collector", real_time=True, max_players=1, factory=_factory)
