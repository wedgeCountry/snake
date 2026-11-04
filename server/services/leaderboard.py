"""Per-user maximum scores per game and mode, stored in the leaderboard
SQLite table (one row per player/game/mode, upserted to the max)."""

from __future__ import annotations

from pathlib import Path

from .db import Db

MODES = ("single", "multi")


class SqliteLeaderboardService:
    def __init__(self, db_path: Path) -> None:
        self._db = Db(db_path)

    def _check_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown mode: {mode}")

    def submit(self, user_id: str, game_id: str, mode: str, score: int) -> int:
        self._check_mode(mode)
        best = max(self.get_best(user_id, game_id, mode), score)
        self._db.execute(
            "INSERT INTO leaderboard (player_id, game_id, mode, score) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(player_id, game_id, mode) DO UPDATE SET score = excluded.score",
            (user_id, game_id, mode, best))
        return best

    def get_best(self, user_id: str, game_id: str, mode: str) -> int:
        self._check_mode(mode)
        row = self._db.query_one(
            "SELECT score FROM leaderboard WHERE player_id = ? AND game_id = ? AND mode = ?",
            (user_id, game_id, mode))
        return int(row["score"]) if row else 0

    def top(self, game_id: str, mode: str, limit: int = 10) -> list[dict]:
        self._check_mode(mode)
        rows = self._db.query(
            "SELECT player_id, score FROM leaderboard WHERE game_id = ? AND mode = ? "
            "ORDER BY score DESC, player_id LIMIT ?", (game_id, mode, limit))
        return [{"userId": r["player_id"], "score": int(r["score"])} for r in rows]

    def bests(self, user_id: str) -> dict:
        """Cross-game profile: this user's best score per game and mode."""
        rows = self._db.query(
            "SELECT game_id, mode, score FROM leaderboard WHERE player_id = ?", (user_id,))
        out: dict = {}
        for r in rows:
            out.setdefault(r["game_id"], {})[r["mode"]] = int(r["score"])
        return out
