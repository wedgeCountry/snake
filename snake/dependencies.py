"""Dependency injection wiring. Swap implementations here (e.g. in tests)."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends

from .contracts import GameService, ScoreService, SettingsService
from .loop import GameLoop
from .core.game import InMemoryGameService
from .services.score import JsonFileScoreService
from .services.settings import JsonFileSettingsService

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_game_service: GameService = InMemoryGameService()
_score_service: ScoreService = JsonFileScoreService(DATA_DIR / "scores.json")
_settings_service: SettingsService = JsonFileSettingsService(DATA_DIR / "settings.json")
_game_loop: GameLoop | None = None


def get_game_service() -> GameService:
    return _game_service


def get_score_service() -> ScoreService:
    return _score_service


def get_settings_service() -> SettingsService:
    return _settings_service


def get_game_loop() -> GameLoop:
    global _game_loop
    if _game_loop is None:
        _game_loop = GameLoop(_game_service, _score_service)
    return _game_loop


def override_services(
    game: GameService | None = None,
    score: ScoreService | None = None,
    settings: SettingsService | None = None,
    loop: GameLoop | None = None,
) -> None:
    global _game_service, _score_service, _settings_service, _game_loop
    if game is not None:
        _game_service = game
    if score is not None:
        _score_service = score
    if settings is not None:
        _settings_service = settings
    _game_loop = loop
