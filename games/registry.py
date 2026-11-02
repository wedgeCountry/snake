"""Game registry: games register themselves; routes resolve by game_id."""

from __future__ import annotations

import random
from typing import Callable

from .engine import Game, GameInfo

_REGISTRY: dict[str, GameInfo] = {}


def register(game_id: str, name: str, real_time: bool, max_players: int,
             factory: Callable[[random.Random | None], Game]) -> None:
    if game_id in _REGISTRY:
        raise ValueError(f"game already registered: {game_id}")
    _REGISTRY[game_id] = GameInfo(
        id=game_id, name=name, real_time=real_time,
        max_players=max_players, factory=factory,
    )


def get(game_id: str) -> GameInfo:
    try:
        return _REGISTRY[game_id]
    except KeyError:
        raise KeyError(f"unknown game: {game_id}") from None


def list_games() -> list[dict]:
    return [
        {"id": g.id, "name": g.name, "realTime": g.real_time, "maxPlayers": g.max_players}
        for g in _REGISTRY.values()
    ]
