"""Dungeon game entry: registers "dungeon" (single-player RPG)."""

from __future__ import annotations

import copy
import random

from ..engine import Game
from ..registry import register
from .core import DungeonGame, DungeonState


def _factory(rng: random.Random | None) -> Game:
    return DungeonGame(rng=rng)


def _serialize(state) -> dict:
    if not isinstance(state, DungeonState):
        return {}
    return {
        "gridSize": state.grid_size,
        "hero": copy.deepcopy(state.hero),
        "monsters": [copy.deepcopy(m) for m in state.monsters],
        "potions": [list(p) for p in state.potions],
        "score": state.score,
        "turn": state.turn,
        "maxTurns": state.max_turns,
        "status": state.status,
        "stepTimeMs": state.step_time_ms,
        "combatLog": list(state.combat_log),
        "difficulty": state.difficulty,
        "levelDifficulty": state.level_difficulty,
    }


register("dungeon", name="Dungeon Quest", real_time=True, max_players=1,
         factory=_factory, serialize=_serialize)
