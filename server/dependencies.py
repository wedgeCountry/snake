"""Dependency providers. Services live on app.state (set in the lifespan);
tests replace them directly on app.state. Sessions are resolved from the
session cookie."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request
from typing import Any

from .contracts import (
    SESSION_COOKIE,
    LeaderboardService,
    ScoreService,
    SessionService,
    SettingsService,
    UserService,
)
from .services.leaderboard import JsonFileLeaderboardService
from .services.score import JsonFileScoreService
from .services.settings import JsonFileSettingsService
from .services.user import CookieUserService

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def build_services(data_dir: Path = DATA_DIR):
    score: ScoreService = JsonFileScoreService(data_dir / "scores.json")
    settings: SettingsService = JsonFileSettingsService(data_dir / "settings.json")
    user: UserService = CookieUserService()
    leaderboard: LeaderboardService = JsonFileLeaderboardService(data_dir / "leaderboard.json")
    return score, settings, user, leaderboard


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
