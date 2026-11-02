"""Collector rule configuration (reference for the generic rule contract)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..engine import RuleConfig

GRID_SIZE = 8
DOT_COUNT = 5


@dataclass(frozen=True)
class CollectorConfig(RuleConfig):
    grid_size: int = GRID_SIZE
    dot_count: int = DOT_COUNT
    step_time_ms: int = 200
    weights: dict[str, int] = field(default_factory=lambda: {"dot": 1})
    durations_s: dict[str, float | None] = field(default_factory=lambda: {"dot": None})
