"""Shared grid movement primitives.

`candidate_head` computes the next cell for a 3D move: torus wraps around,
otherwise leaving the grid kills. `clamp2d` is the 2D variant that stops at
the border instead of dying.
"""

from __future__ import annotations

from typing import Sequence

from .direction import Direction

Cell3 = tuple[int, int, int]


def candidate_head(head: Sequence[int], direction: Direction, n: int, torus: bool) -> Cell3 | None:
    """Next head cell after moving `head` by `direction` on an n^3 grid.
    Returns None when the move leaves the grid and torus is off (wall death)."""
    c = (head[0] + direction.x, head[1] + direction.y, head[2] + direction.z)
    if torus:
        return (c[0] % n, c[1] % n, c[2] % n)
    if all(0 <= v < n for v in c):
        return c
    return None


def clamp2d(x: int, y: int, n: int) -> tuple[int, int]:
    """Clamp an (x, y) position into the n x n grid (2D games: no wall death)."""
    return (min(max(x, 0), n - 1), min(max(y, 0), n - 1))
