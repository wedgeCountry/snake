"""Dependency providers. Services live on app.state (set in the lifespan);
tests replace them directly on app.state. All persistent services share one
SQLite database file (data/games.db). Sessions are resolved from the
session cookie."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request
from typing import Any

from .contracts import (
    SESSION_COOKIE,
    LeaderboardService,
    SavegameService,
    ScoreService,
    SessionService,
    SettingsService,
    UserService,
)
from .services.leaderboard import SqliteLeaderboardService
from .services.savegame import SqliteSavegameService
from .services.score import SqliteScoreService
from .services.settings import SqliteSettingsService
from .services.user import CookieUserService

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "games.db"


def build_services(data_dir: Path = DATA_DIR):
    db = data_dir / "games.db"
    score: ScoreService = SqliteScoreService(db)
    settings: SettingsService = SqliteSettingsService(db)
    user: UserService = CookieUserService()
    leaderboard: LeaderboardService = SqliteLeaderboardService(db)
    savegames: SavegameService = SqliteSavegameService(db)
    return score, settings, user, leaderboard, savegames


def get_session_service(request: Request) -> SessionService:
    return request.app.state.session_service


def get_session(request: Request, sessions: Any = None):
    sessions = sessions or request.app.state.session_service
    session_id = request.cookies.get(SESSION_COOKIE)
    session = sessions.get(session_id) if session_id else None
    if session is None:
        raise HTTPException(status_code=404, detail="no active session")
    sessions.touch(session_id)
    return session


def get_score_service(request: Request) -> ScoreService:
    return request.app.state.score_service


def get_settings_service(request: Request) -> SettingsService:
    return request.app.state.settings_service


def get_user_service(request: Request) -> UserService:
    return request.app.state.user_service


def get_leaderboard_service(request: Request) -> LeaderboardService:
    return request.app.state.leaderboard_service


def get_savegame_service(request: Request) -> SavegameService:
    return request.app.state.savegame_service
