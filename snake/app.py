from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .contracts import GameService, ScoreService, SettingsService
from .dependencies import (
    build_services,
    get_game_loop,
    get_game_service,
    get_score_service,
    get_settings_service,
)
from .loop import GameLoop
from .models import Direction
from .schemas import DirectionRequest, NewGameRequest, SettingsRequest

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    if not hasattr(fastapi_app.state, "game_service"):
        game, score, settings = build_services()
        fastapi_app.state.game_service = game
        fastapi_app.state.score_service = score
        fastapi_app.state.settings_service = settings
    if not hasattr(fastapi_app.state, "game_loop"):
        fastapi_app.state.game_loop = GameLoop(
            fastapi_app.state.game_service, fastapi_app.state.score_service
        )
    loop = fastapi_app.state.game_loop
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


@app.post("/api/direction")
def post_direction(
    req: DirectionRequest,
    game: GameService = Depends(get_game_service),
) -> dict:
    game.set_direction(Direction.from_name(req.direction))
    return game.state().to_dict()


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
