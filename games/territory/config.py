"""Territory (strategy) rule configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..engine import RuleConfig

GRID_SIZE = 9
MINE_COUNT = 6
MINE_BONUS = 15
MAX_TURNS = 80
TERRITORY_GOAL = 45  # cells needed to win at the turn limit
SCORE_PER_CELL = 5


@dataclass(frozen=True)
class TerritoryConfig(RuleConfig):
    grid_size: int = GRID_SIZE
    mine_count: int = MINE_COUNT
    mine_bonus: int = MINE_BONUS
    max_turns: int = MAX_TURNS
    territory_goal: int = TERRITORY_GOAL
    score_per_cell: int = SCORE_PER_CELL
    step_time_ms: int = 300
    weights: dict[str, int] = field(default_factory=lambda: {"mine": 1})
    durations_s: dict[str, float | None] = field(default_factory=lambda: {"mine": None})
