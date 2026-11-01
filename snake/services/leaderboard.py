from __future__ import annotations

import json
from pathlib import Path

MODES = ("single", "multi")


class JsonFileLeaderboardService:
    """Per-user maximum scores for the single-play and multiplayer boards,
    persisted to a JSON file, cached in memory."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._boards = self._read()

    def _empty(self) -> dict:
        return {mode: {} for mode in MODES}

    def _read(self) -> dict:
        try:
            data = json.loads(self._path.read_text())
            boards = self._empty()
            if isinstance(data, dict):
                for mode in MODES:
                    entries = data.get(mode)
                    if isinstance(entries, dict):
                        boards[mode] = {str(k): int(v) for k, v in entries.items()}
            return boards
        except (OSError, ValueError, json.JSONDecodeError):
            return self._empty()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._boards))

    def submit(self, user_id: str, mode: str, score: int) -> int:
        """Register the user's maximum score for the mode; returns the max."""
        if mode not in MODES:
            raise ValueError(f"unknown mode: {mode}")
        board = self._boards[mode]
        best = max(board.get(user_id, 0), score)
        board[user_id] = best
        self._save()
        return best

    def get_best(self, user_id: str, mode: str) -> int:
        if mode not in MODES:
            raise ValueError(f"unknown mode: {mode}")
        return self._boards[mode].get(user_id, 0)

    def top(self, mode: str, limit: int = 10) -> list[dict]:
        if mode not in MODES:
            raise ValueError(f"unknown mode: {mode}")
        entries = sorted(self._boards[mode].items(), key=lambda kv: kv[1], reverse=True)
        return [{"userId": uid, "score": score} for uid, score in entries[:limit]]
