from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DIRECTION_PATTERN = "^(left|right|up|down|forward|back)$"

LeaderboardMode = Literal["single", "multi"]


class DirectionRequest(BaseModel):
    direction: str = Field(pattern=DIRECTION_PATTERN)
    player: int = Field(default=0, ge=0, le=1)


class NewGameRequest(BaseModel):
    torus: bool = True
    mode: LeaderboardMode = "single"


class SettingsRequest(BaseModel):
    step_time_ms: int | None = Field(default=None, ge=60, le=400)
    torus: bool | None = None
