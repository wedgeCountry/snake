"""Dependency providers. Services live on app.state (set in the lifespan);
tests replace them via app.dependency_overrides."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request

from .contracts import GameService, LeaderboardService, ScoreService, SettingsService, UserService
from .core.game import InMemoryGameService
from .loop import GameLoop
from .services.leaderboard import JsonFileLeaderboardService
from .services.score import JsonFileScoreService
from .services.settings import JsonFileSettingsService
from .services.user import CookieUserService

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def build_services(
    data_dir: Path = DATA_DIR,
) -> tuple[GameService, ScoreService, SettingsService, UserService, LeaderboardService]:
    game: GameService = InMemoryGameService()
    score: ScoreService = JsonFileScoreService(data_dir / "scores.json")
    settings: SettingsService = JsonFileSettingsService(data_dir / "settings.json")
    user: UserService = CookieUserService()
    leaderboard: LeaderboardService = JsonFileLeaderboardService(data_dir / "leaderboard.json")
    return game, score, settings, user, leaderboard


def get_game_service(request: Request) -> GameService:
    return request.app.state.game_service


def get_score_service(request: Request) -> ScoreService:
    return request.app.state.score_service


def get_settings_service(request: Request) -> SettingsService:
    return request.app.state.settings_service


def get_game_loop(request: Request) -> GameLoop:
    return request.app.state.game_loop


def get_user_service(request: Request) -> UserService:
    return request.app.state.user_service


def get_leaderboard_service(request: Request) -> LeaderboardService:
    return request.app.state.leaderboard_service
