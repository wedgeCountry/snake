"""Shared weighted spawner for grid games: pick a free cell and a weighted
kind, plus the timed-despawn check for expiring entities."""

from __future__ import annotations

import random
from typing import Sequence

from .board import weighted_choice


class WeightedSpawner:
    """Spawns (cell, kind) pairs on free cells with per-kind weights."""

    def __init__(self, rng: random.Random, weights: Sequence[tuple[str, int]]) -> None:
        self._rng = rng
        self._weights = list(weights)

    def spawn(self, free_cells: Sequence[tuple]) -> tuple[tuple, str] | None:
        if not free_cells:
            return None
        return self._rng.choice(list(free_cells)), weighted_choice(self._rng, self._weights)


def should_despawn(age_ms: int, kind: str, durations_s: dict[str, float | None], step_ms: int) -> bool:
    """True when the entity of `kind` has been on the board for its full
    duration (durations_s None = never despawns). `age_ms` is the age before
    this tick; the tick's own step_ms counts toward the age."""
    duration = durations_s.get(kind)
    if duration is None:
        return False
    return age_ms + step_ms >= duration * 1000
