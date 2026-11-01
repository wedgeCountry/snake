from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .contracts import GameService, ScoreService, SettingsService
from .dependencies import (
    get_game_loop,
    get_game_service,
    get_score_service,
    get_settings_service,
)
from .loop import GameLoop
from .models import Direction

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    loop = get_game_loop()
    if not loop.running:
        await loop.start()
    yield
    await loop.stop()


app = FastAPI(title="3D Snake", lifespan=lifespan)


@app.get("/api/state")
def get_state(
    game: GameService = Depends(get_game_service),
    score: ScoreService = Depends(get_score_service),
    settings: SettingsService = Depends(get_settings_service),
) -> dict:
    state = game.state().to_dict()
    state["best"] = score.get_best()
    state["stepTimeMs"] = settings.get_step_time_ms()
    state["torus"] = settings.get_torus()
    return state


class DirectionRequest(BaseModel):
    direction: str = Field(pattern="^(left|right|up|down|forward|back)$")


@app.post("/api/direction")
def post_direction(
    req: DirectionRequest,
    game: GameService = Depends(get_game_service),
) -> dict:
    game.set_direction(Direction.from_name(req.direction))
    return game.state().to_dict()


class StepRequest(BaseModel):
    action: str | None = Field(default=None, pattern="^(left|right|up|down|forward|back)$")


@app.post("/api/step")
def post_step(
    req: StepRequest | None = None,
    loop: GameLoop = Depends(get_game_loop),
) -> dict:
    return loop.step(req.action if req else None).to_dict()


@app.post("/api/gameover")
def post_gameover(
    score: ScoreService = Depends(get_score_service),
    game: GameService = Depends(get_game_service),
) -> dict:
    best = score.submit(game.state().score)
    return {"score": game.state().score, "best": best}


class NewGameRequest(BaseModel):
    torus: bool = True


@app.post("/api/new")
async def post_new_game(
    req: NewGameRequest,
    game: GameService = Depends(get_game_service),
    settings: SettingsService = Depends(get_settings_service),
    loop: GameLoop = Depends(get_game_loop),
) -> dict:
    settings.set_torus(req.torus)
    state = game.new_game(torus=req.torus, step_time_ms=settings.get_step_time_ms())
    loop.activate()
    if not loop.running:
        await loop.start()
    return state.to_dict()


class SettingsRequest(BaseModel):
    step_time_ms: int | None = Field(default=None, ge=60, le=400)
    torus: bool | None = None


@app.post("/api/settings")
def post_settings(
    req: SettingsRequest,
    settings: SettingsService = Depends(get_settings_service),
) -> dict:
    if req.step_time_ms is not None:
        settings.set_step_time_ms(req.step_time_ms)
    if req.torus is not None:
        settings.set_torus(req.torus)
    return {"stepTimeMs": settings.get_step_time_ms(), "torus": settings.get_torus()}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
