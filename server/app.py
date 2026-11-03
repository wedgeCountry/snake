"""FastAPI app: generic game routes over the registry + session service.

Clients only submit actions and read state; the server owns all state
transitions. All game state is session-scoped — nothing mutable lives on
app.state as a singleton game. One authoritative stepper per session: the
SessionLoop task ticks the game; the WebSocket transport only pushes state.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from games import list_games
from games.registry import get as get_game_info
from .contracts import (
    SESSION_COOKIE,
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
from .schemas import ActionRequest, NewGameRequest, SettingsRequest
from .services.user import COOKIE_NAME
from .session import InMemorySessionService, SessionLoop

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _make_session_service(app_state) -> InMemorySessionService:
    """Session service whose expiry cancels and removes the session's loop."""
    async def _cancel(sid: str) -> None:
        loop = app_state.session_loops.pop(sid, None)
        if loop is not None:
            await loop.stop()
    service = InMemorySessionService()
    service._on_expire = lambda sid: asyncio.ensure_future(_cancel(sid))
    return service


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    if not hasattr(fastapi_app.state, "session_service"):
        score, settings, user, leaderboard = build_services()
        fastapi_app.state.session_loops = {}
        fastapi_app.state.session_service = _make_session_service(fastapi_app.state)
        fastapi_app.state.score_service = score
        fastapi_app.state.settings_service = settings
        fastapi_app.state.user_service = user
        fastapi_app.state.leaderboard_service = leaderboard
    yield
    for loop in list(fastapi_app.state.session_loops.values()):
        await loop.stop()
    fastapi_app.state.session_loops.clear()


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


def _session_for_game(session, game_id: str):
    """A session cookie is only valid for the game that created it."""
    if session is None or session.game_id != game_id:
        raise HTTPException(status_code=404, detail="no active session")
    return session


def _envelope_for(session, user_id: str, score: ScoreService,
                  settings: SettingsService, leaderboard: LeaderboardService) -> dict:
    state = session.game.state()
    state_dict = get_game_info(session.game_id).serialize(state)
    meta = {
        "best": score.get_best(session.game_id),
        "userBest": leaderboard.get_best(user_id, session.game_id, session.mode),
        "stepTimeMs": settings.get_step_time_ms(user_id),
        "torus": settings.get_torus(user_id),
        "userId": user_id,
        "leaderboard": leaderboard.top(session.game_id, session.mode),
    }
    return envelope(session.game_id, session, state_dict, [session.user_id],
                    state.status if hasattr(state, "status") else "running", meta)


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
    info = get_game_info(game_id)
    user_id, is_new = _resolve_user(request, user)
    settings.set(user_id, {"torus": req.torus})
    session_id = sessions.create(game_id, user_id, req.mode)
    session = sessions.get(session_id)
    # the game's own registered builder maps user settings + request to its config
    cfg = info.build_config(settings.get(user_id), req.mode, req.torus)
    session.game.init(cfg)
    loops = request.app.state.session_loops

    def _drop_loop() -> None:
        loops.pop(session_id, None)

    loop = SessionLoop(session, score, leaderboard, on_finished=_drop_loop)
    loops[session_id] = loop
    await loop.start()
    body = _envelope_for(session, user_id, score, settings, leaderboard)
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
    _session_for_game(session, game_id)
    body = _envelope_for(session, user_id, score, settings, leaderboard)
    return _with_cookies(JSONResponse(body), user_id, is_new, None, False)


@app.post("/api/games/{game_id}/action")
def api_action(
    game_id: str,
    req: ActionRequest,
    session: Any = Depends(get_session),
) -> dict:
    if req.player >= get_game_info(game_id).max_players:
        raise HTTPException(status_code=422, detail=f"player out of range for {game_id}")
    _session_for_game(session, game_id)
    session.game.apply_action(req.player, {**req.action, "player": req.player})
    return {"ok": True}


@app.post("/api/settings")
def api_settings(
    req: SettingsRequest,
    request: Request,
    sessions: SessionService = Depends(get_session_service),
    settings: SettingsService = Depends(get_settings_service),
    user: UserService = Depends(get_user_service),
) -> JSONResponse:
    user_id, is_new = _resolve_user(request, user)
    patch: dict = {}
    if req.step_time_ms is not None:
        patch["stepTimeMs"] = settings.set_step_time_ms(user_id, req.step_time_ms)
        # apply live to the active session: the loop and the WS transport
        # re-read state.step_time_ms on every tick, so the speed slider
        # takes effect immediately instead of only on the next new game
        session_id = request.cookies.get(SESSION_COOKIE)
        session = sessions.get(session_id) if session_id else None
        if session is not None:
            state = session.game.state()
            if hasattr(state, "step_time_ms"):
                state.step_time_ms = patch["stepTimeMs"]
    if req.torus is not None:
        patch["torus"] = settings.set_torus(user_id, req.torus)
    body = patch or {"stepTimeMs": settings.get_step_time_ms(user_id), "torus": settings.get_torus(user_id)}
    response = JSONResponse(body)
    if is_new:
        response.set_cookie(COOKIE_NAME, user_id, max_age=365 * 24 * 3600, httponly=True, samesite="lax")
    return response


@app.get("/api/users/me/stats")
def api_user_stats(
    request: Request,
    leaderboard: LeaderboardService = Depends(get_leaderboard_service),
    user: UserService = Depends(get_user_service),
) -> JSONResponse:
    """Cross-game user profile: the caller's best score per game and mode."""
    user_id, is_new = _resolve_user(request, user)
    response = JSONResponse({"userId": user_id, "bests": leaderboard.bests(user_id)})
    if is_new:
        response.set_cookie(COOKIE_NAME, user_id, max_age=365 * 24 * 3600, httponly=True, samesite="lax")
    return response


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
    """Real-time transport: pushes the versioned envelope on each loop tick.
    Push-only — the session's SessionLoop is the single authoritative stepper."""
    await websocket.accept()
    session_id = websocket.query_params.get("session")
    loop = websocket.app.state.session_loops.get(session_id or "")
    if loop is None or loop._session.game_id != game_id:
        await websocket.close(code=4404)
        return
    session = loop._session
    try:
        while True:
            state = session.game.state()
            payload = get_game_info(game_id).serialize(state)
            meta = {
                "best": websocket.app.state.score_service.get_best(game_id),
                "userBest": websocket.app.state.leaderboard_service.get_best(
                    session.user_id, game_id, session.mode),
                "userId": session.user_id,
            }
            await websocket.send_json(envelope(
                game_id, session, payload, [session.user_id],
                state.status if hasattr(state, "status") else "running", meta))
            if session.game.is_terminal():
                break
            step_ms = getattr(state, "step_time_ms", 260)
            await asyncio.sleep(step_ms / 1000.0)
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close(code=1011)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
