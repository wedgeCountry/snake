"""Snake game entry: registers "snake" in the game registry."""

from __future__ import annotations

import random

from ..engine import Game
from ..registry import register
from .core import SnakeGame


def _factory(rng: random.Random | None) -> Game:
    return SnakeGame(rng=rng)


register("snake", name="3D Snake", real_time=True, max_players=2, factory=_factory)
