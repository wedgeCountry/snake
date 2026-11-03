"""Snake game entry: registers "snake" in the game registry."""

from __future__ import annotations

import random

from ..engine import Game
from ..registry import register
from .config import DEFAULT_STEP_MS, MAX_STEP_MS, MIN_STEP_MS, SnakeConfig
from .core import SnakeGame
from .dto import SnakeStateDTO


def _factory(rng: random.Random | None) -> Game:
    return SnakeGame(rng=rng)


def _build_config(user_settings: dict, mode: str, torus: bool) -> SnakeConfig:
    """Snake-specific config built from per-user settings + the new-game request,
    so the generic routes never import SnakeConfig themselves."""
    try:
        step = int(user_settings.get("stepTimeMs", DEFAULT_STEP_MS))
    except (TypeError, ValueError):
        step = DEFAULT_STEP_MS
    step = min(MAX_STEP_MS, max(MIN_STEP_MS, step))
    return SnakeConfig(step_time_ms=step, torus=torus, mode=mode)


register("snake", name="3D Snake", real_time=True, max_players=2,
         factory=_factory, serialize=lambda s: SnakeStateDTO.from_state(s).to_dict(),
         build_config=_build_config)
