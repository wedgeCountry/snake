from __future__ import annotations

from pydantic import BaseModel, Field

DIRECTION_PATTERN = "^(left|right|up|down|forward|back)$"


class DirectionRequest(BaseModel):
    direction: str = Field(pattern=DIRECTION_PATTERN)


class NewGameRequest(BaseModel):
    torus: bool = True


class SettingsRequest(BaseModel):
    step_time_ms: int | None = Field(default=None, ge=60, le=400)
    torus: bool | None = None
