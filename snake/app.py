"""FastAPI app: generic game routes over the registry + session service.

Clients only submit actions and read state; the server owns all state
transitions. All game state is session-scoped — nothing mutable lives on
app.state as a singleton game.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from typing import Any

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from games import list_games
from games.snake.config import SnakeConfig
from games.snake.dto import SnakeStateDTO
from .contracts import (
    ENVELOPE_VERSION,
    LeaderboardService,
    ScoreService,
    SessionService,
    SettingsService,
    UserService,
    envelope,
)
from .dependencies import (
    build_services,
    get_leaderboard_service,
    get_score_service,
    get_session,
    get_session_service,
    get_settings_service,
    get_user_service,
)
from .contracts import SESSION_COOKIE
from .schemas import ActionRequest, NewGameRequest, SettingsRequest
from .services.user import COOKIE_NAME
from .session import InMemorySessionService, SessionLoop

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    if not hasattr(fastapi_app.state, "session_service"):
        score, settings, user, leaderboard = build_services()
        fastapi_app.state.session_service = InMemorySessionService()
        fastapi_app.state.score_service = score
        fastapi_app.state.settings_service = settings
        fastapi_app.state.user_service = user
        fastapi_app.state.leaderboard_service = leaderboard
        fastapi_app.state.session_loops = {}
    yield
    for loop in list(fastapi_app.state.session_loops.values()):
        await loop.stop()


app = FastAPI(title="Game Platform", lifespan=lifespan)


def _resolve_user(request: Request, user: UserService) -> tuple[str, bool]:
    """Return (user_id, is_new); is_new means the ID cookie must be set."""
    return user.resolve(request.cookies.get(user.cookie_name)), request.cookies.get(user.cookie_name) is None


def _with_cookies(response: JSONResponse, user_id: str, is_new: bool,
                  session_id: str | None, is_new_session: bool) -> JSONResponse:
    if is_new:
        response.set_cookie(COOKIE_NAME, user_id, max_age=365 * 24 * 3600, httponly=True, samesite="lax")
    if is_new_session and session_id:
        response.set_cookie(SESSION_COOKIE, session_id, max_age=365 * 24 * 3600, httponly=True, samesite="lax")
    return response


def _envelope_for(session, user_id: str, score: ScoreService,
                  settings: SettingsService, leaderboard: LeaderboardService) -> dict:
    game = session.game
    state = game.state()
    if session.game_id == "snake":
        state_dict = SnakeStateDTO.from_state(state).to_dict()
    elif session.game_id == "collector":
        from games.collector.core import CollectorState
        st = state if isinstance(state, CollectorState) else None
        state_dict = {"pos": list(st.pos), "dots": [list(d) for d in st.dots],
                      "score": st.score, "gridSize": st.grid_size} if st else {}
    state_dict["best"] = score.get_best(session.game_id)
    state_dict["stepTimeMs"] = settings.get_step_time_ms(user_id)
    state_dict["torus"] = settings.get_torus(user_id)
    state_dict["userId"] = user_id
    state_dict["leaderboard"] = leaderboard.top(session.game_id, session.mode)
    return envelope(session.game_id, session, state_dict, [session.user_id],
                    state.status if hasattr(state, "status") else "running")


@app.get("/api/games")
def api_games() -> list[dict]:
    return list_games()


@app.post("/api/games/{game_id}/new")
async def api_new_game(
    game_id: str,
    req: NewGameRequest,
    request: Request,
    sessions: SessionService = Depends(get_session_service),
    score: ScoreService = Depends(get_score_service),
    settings: SettingsService = Depends(get_settings_service),
    user: UserService = Depends(get_user_service),
    leaderboard: LeaderboardService = Depends(get_leaderboard_service),
) -> JSONResponse:
    user_id, is_new = _resolve_user(request, user)
    settings.set(user_id, {"torus": req.torus})
    session_id = sessions.create(game_id, user_id, req.mode)
    session = sessions.get(session_id)
    cfg = SnakeConfig(step_time_ms=settings.get_step_time_ms(user_id), torus=req.torus, mode=req.mode)
    session.game.init(cfg)
    loop = SessionLoop(session, score, leaderboard)
    request.app.state.session_loops[session_id] = loop
    await loop.start()
    body = _envelope_for(session, user_id, score, settings, leaderboard)
    body["v"] = ENVELOPE_VERSION
    return _with_cookies(JSONResponse(body), user_id, is_new, session_id, True)


@app.get("/api/games/{game_id}/state")
def api_state(
    game_id: str,
    request: Request,
    session: Any = Depends(get_session),
    score: ScoreService = Depends(get_score_service),
    settings: SettingsService = Depends(get_settings_service),
    user: UserService = Depends(get_user_service),
    leaderboard: LeaderboardService = Depends(get_leaderboard_service),
) -> JSONResponse:
    user_id, is_new = _resolve_user(request, user)
    body = _envelope_for(session, user_id, score, settings, leaderboard)
    return _with_cookies(JSONResponse(body), user_id, is_new, None, False)


@app.post("/api/games/{game_id}/action")
def api_action(
    game_id: str,
    req: ActionRequest,
    session: Any = Depends(get_session),
) -> dict:
    session.game.apply_action(req.player, {**req.action, "player": req.player})
    return {"ok": True}


@app.post("/api/settings")
def api_settings(
    req: SettingsRequest,
    request: Request,
    settings: SettingsService = Depends(get_settings_service),
    user: UserService = Depends(get_user_service),
) -> dict:
    user_id, _ = _resolve_user(request, user)
    patch: dict = {}
    if req.step_time_ms is not None:
        patch["stepTimeMs"] = settings.set_step_time_ms(user_id, req.step_time_ms)
    if req.torus is not None:
        patch["torus"] = settings.set_torus(user_id, req.torus)
    return patch or {"stepTimeMs": settings.get_step_time_ms(user_id), "torus": settings.get_torus(user_id)}


@app.get("/api/leaderboard/{game_id}/{mode}")
def api_leaderboard(
    game_id: str,
    mode: str,
    leaderboard: LeaderboardService = Depends(get_leaderboard_service),
) -> dict:
    if mode not in ("single", "multi"):
        return {"gameId": game_id, "mode": mode, "top": []}
    return {"gameId": game_id, "mode": mode, "top": leaderboard.top(game_id, mode)}


@app.websocket("/ws/games/{game_id}")
async def ws_game(websocket: WebSocket, game_id: str):
    """Real-time transport: pushes the versioned envelope after each tick."""
    await websocket.accept()
    session_id = websocket.query_params.get("session")
    sessions: SessionService = websocket.app.state.session_service
    loop = websocket.app.state.session_loops.get(session_id or "")
    if loop is None:
        await websocket.close(code=4404)
        return
    try:
        while True:
            loop.step()
            state = loop._session.game.state()
            if game_id == "snake":
                payload = SnakeStateDTO.from_state(state).to_dict()
            elif game_id == "collector":
                from games.collector.core import CollectorState
                payload = ({"pos": list(state.pos), "dots": [list(d) for d in state.dots],
                            "score": state.score, "gridSize": state.grid_size}
                           if isinstance(state, CollectorState) else {})
            await websocket.send_json(envelope(
                game_id, loop._session, payload, [loop._session.user_id],
                state.status if hasattr(state, "status") else "running"))
            step_ms = getattr(state, "step_time_ms", 260)
            import asyncio
            await asyncio.sleep(step_ms / 1000.0)
    except WebSocketDisconnect:
        pass


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
