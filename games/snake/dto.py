"""Snake wire DTOs. The `Serializable` protocol belongs to DTO classes;
the domain model has no to_dict()."""

from __future__ import annotations

from .models import SnakeState


class SnakeStateDTO:
    state_schema_version = 1

    def __init__(self, data: dict) -> None:
        self._data = data

    @classmethod
    def from_state(cls, state: SnakeState) -> "SnakeStateDTO":
        return cls({
            "gridSize": state.grid_size,
            "snake": [{"x": c.x, "y": c.y, "z": c.z} for c in state.snake],
            "snakes": [[{"x": c.x, "y": c.y, "z": c.z} for c in s] for s in state.snakes],
            "direction": {"x": state.direction.x, "y": state.direction.y, "z": state.direction.z},
            "directions": [{"x": d.x, "y": d.y, "z": d.z} for d in state.directions],
            "food": {"x": state.food.x, "y": state.food.y, "z": state.food.z, "kind": state.food.kind.value},
            "score": state.score,
            "scores": list(state.scores),
            "stepTimeMs": state.step_time_ms,
            "torus": state.torus,
            "status": state.status,
            "mode": state.mode,
            "loser": state.loser,
            "starSteps": list(state.star_steps),
            "fruitAgeMs": state.fruit_age_ms,
            "fruitDurationMs": _fruit_duration_ms(state),
        })

    def to_dict(self) -> dict:
        return dict(self._data)


def _fruit_duration_ms(state: SnakeState) -> int | None:
    from .config import DEFAULT_DURATIONS_S
    seconds = DEFAULT_DURATIONS_S.get(state.food.kind)
    return None if seconds is None else int(seconds * 1000)
