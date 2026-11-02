"""Shared grid-occupancy and spawn helpers for grid-based games."""

from __future__ import annotations

import random
from typing import Iterable, Sequence

Cell = tuple[int, int, int]


def free_cells(grid_size: int, occupied: Iterable[Cell], extra: Iterable[Cell] = ()) -> list[Cell]:
    occ = set(occupied) | set(extra)
    return [
        (x, y, z)
        for x in range(grid_size)
        for y in range(grid_size)
        for z in range(grid_size)
        if (x, y, z) not in occ
    ]


def weighted_choice(rng: random.Random, weights: Sequence[tuple[str, int]]) -> str:
    kinds = [k for k, _ in weights]
    vals = [w for _, w in weights]
    return rng.choices(kinds, weights=vals, k=1)[0]
