from __future__ import annotations

import json
from pathlib import Path

MODES = ("single", "multi")


class JsonFileLeaderboardService:
    """Per-user maximum scores per game and mode, persisted to a JSON file,
    cached in memory."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._boards = self._read()

    def _empty(self) -> dict:
        return {}

    def _read(self) -> dict:
        try:
            data = json.loads(self._path.read_text())
            if not isinstance(data, dict):
                return {}
            return {
                str(game_id): {
                    str(mode): {str(u): int(s) for u, s in users.items()}
                    for mode, users in modes.items() if isinstance(users, dict)
                }
                for game_id, modes in data.items() if isinstance(modes, dict)
            }
        except (OSError, ValueError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._boards))

    def _board(self, game_id: str, mode: str) -> dict:
        if mode not in MODES:
            raise ValueError(f"unknown mode: {mode}")
        return self._boards.setdefault(game_id, {}).setdefault(mode, {})

    def submit(self, user_id: str, game_id: str, mode: str, score: int) -> int:
        board = self._board(game_id, mode)
        best = max(board.get(user_id, 0), score)
        board[user_id] = best
        self._save()
        return best

    def get_best(self, user_id: str, game_id: str, mode: str) -> int:
        return self._board(game_id, mode).get(user_id, 0)

    def top(self, game_id: str, mode: str, limit: int = 10) -> list[dict]:
        board = self._board(game_id, mode)
        entries = sorted(board.items(), key=lambda kv: kv[1], reverse=True)
        return [{"userId": uid, "score": score} for uid, score in entries[:limit]]
