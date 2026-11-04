from __future__ import annotations

from pydantic import BaseModel, Field

DIRECTION_PATTERN = "^(left|right|up|down|forward|back)$"


class NewGameRequest(BaseModel):
    mode: str = "single"
    torus: bool = True


class ActionRequest(BaseModel):
    player: int = Field(default=0, ge=0)
    action: dict = Field(default_factory=dict)


class SettingsRequest(BaseModel):
    step_time_ms: int | None = Field(default=None, ge=60, le=400)
    torus: bool | None = None


class SaveRequest(BaseModel):
    name: str = ""
