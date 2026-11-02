"""Top-level games package: every game is a pure core plus config/effects/DTO."""

from . import collector, snake  # noqa: F401  (register games)
from .registry import get, list_games, register

__all__ = ["register", "get", "list_games"]
