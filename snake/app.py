from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .contracts import GameService, LeaderboardService, ScoreService, SettingsService, UserService
from .dependencies import (
    build_services,
    get_game_loop,
    get_game_service,
    get_leaderboard_service,
    get_score_service,
    get_settings_service,
    get_user_service,
)
from .loop import GameLoop
from .models import Direction
from .schemas import DirectionRequest, LeaderboardMode, NewGameRequest, SettingsRequest
from .services.leaderboard import MODES
from .services.user import COOKIE_NAME

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    if not hasattr(fastapi_app.state, "game_service"):
        game, score, settings, user, leaderboard = build_services()
        fastapi_app.state.game_service = game
        fastapi_app.state.score_service = score
        fastapi_app.state.settings_service = settings
        fastapi_app.state.user_service = user
        fastapi_app.state.leaderboard_service = leaderboard
    if not hasattr(fastapi_app.state, "game_loop"):
        fastapi_app.state.game_loop = GameLoop(
            fastapi_app.state.game_service,
            fastapi_app.state.score_service,
            fastapi_app.state.leaderboard_service,
        )
    loop = fastapi_app.state.game_loop
    if not loop.running:
        await loop.start()
    yield
    await loop.stop()


app = FastAPI(title="3D Snake", lifespan=lifespan)


def _resolve_user(request: Request, user: UserService) -> tuple[str, bool]:
    """Return (user_id, is_new); is_new means the ID cookie must be set."""
    return user.resolve(request.cookies.get(user.cookie_name)), request.cookies.get(user.cookie_name) is None


@app.get("/api/state")
def get_state(
    request: Request,
    game: GameService = Depends(get_game_service),
    score: ScoreService = Depends(get_score_service),
    settings: SettingsService = Depends(get_settings_service),
    user: UserService = Depends(get_user_service),
    leaderboard: LeaderboardService = Depends(get_leaderboard_service),
) -> JSONResponse:
    user_id, is_new = _resolve_user(request, user)
    state = game.state().to_dict()
    state["best"] = score.get_best()
    state["stepTimeMs"] = settings.get_step_time_ms()
    state["torus"] = settings.get_torus()
    state["userId"] = user_id
    state["leaderboard"] = leaderboard.top("single")
    response = JSONResponse(state)
    if is_new:
        response.set_cookie(COOKIE_NAME, user_id, max_age=365 * 24 * 3600, httponly=True, samesite="lax")
    return response


@app.post("/api/direction")
def post_direction(
    req: DirectionRequest,
    game: GameService = Depends(get_game_service),
) -> dict:
    game.set_direction(Direction.from_name(req.direction))
    return game.state().to_dict()


@app.post("/api/new")
async def post_new_game(
    request: Request,
    req: NewGameRequest,
    game: GameService = Depends(get_game_service),
    settings: SettingsService = Depends(get_settings_service),
    loop: GameLoop = Depends(get_game_loop),
    user: UserService = Depends(get_user_service),
) -> JSONResponse:
    settings.set_torus(req.torus)
    user_id, is_new = _resolve_user(request, user)
    loop.set_context(user_id, req.mode)
    state = game.new_game(torus=req.torus, step_time_ms=settings.get_step_time_ms())
    loop.activate()
    if not loop.running:
        await loop.start()
    response = JSONResponse(state.to_dict())
    if is_new:
        response.set_cookie(COOKIE_NAME, user_id, max_age=365 * 24 * 3600, httponly=True, samesite="lax")
    return response


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


@app.get("/api/leaderboard/{mode}")
def get_leaderboard(
    mode: LeaderboardMode,
    leaderboard: LeaderboardService = Depends(get_leaderboard_service),
) -> dict:
    if mode not in MODES:
        return {"mode": mode, "top": []}
    return {"mode": mode, "top": leaderboard.top(mode)}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
