"""Snake rule configuration: effect weights and durations declared in one
dataclass — the reference implementation of the pipeline-wide rule contract."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ..engine import RuleConfig
from .models import FruitKind

MIN_STEP_MS = 60
MAX_STEP_MS = 400
DEFAULT_STEP_MS = 260

MIN_GRID_SIZE = 6
MAX_GRID_SIZE = 16
GRID_RESIZE_STEP = 2
STAR_STEPS = 8

DEFAULT_WEIGHTS: list[tuple[FruitKind, int]] = [
    (FruitKind.APPLE, 50),
    (FruitKind.REVERSE, 12),
    (FruitKind.GROW_GRID, 12),
    (FruitKind.SHRINK_GRID, 12),
    (FruitKind.STAR, 14),
]

# How long each fruit kind stays on the board before despawning (None = forever).
DEFAULT_DURATIONS_S: dict[FruitKind, float | None] = {
    FruitKind.APPLE: None,
    FruitKind.REVERSE: 30.0,
    FruitKind.GROW_GRID: 30.0,
    FruitKind.SHRINK_GRID: 30.0,
    FruitKind.STAR: 30.0,
}


@dataclass(frozen=True)
class SnakeConfig(RuleConfig):
    step_time_ms: int = DEFAULT_STEP_MS
    grid_size: int = 10
    torus: bool = True
    mode: str = "single"
    star_steps: int = STAR_STEPS
    fruit_weights: list[tuple[FruitKind, int]] = field(default_factory=lambda: list(DEFAULT_WEIGHTS))
    fruit_durations_s: dict[FruitKind, float | None] = field(
        default_factory=lambda: dict(DEFAULT_DURATIONS_S))

    def __post_init__(self) -> None:
        object.__setattr__(self, "weights", {k.value: w for k, w in self.fruit_weights})
        object.__setattr__(self, "durations_s", {k.value: v for k, v in self.fruit_durations_s.items()})

    def fruit_duration_ms(self, kind: FruitKind) -> int | None:
        seconds = self.fruit_durations_s.get(kind)
        return None if seconds is None else int(seconds * 1000)

    def with_overrides(self, **kwargs) -> "SnakeConfig":
        return replace(self, **kwargs)
