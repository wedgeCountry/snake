"""Best-score bookkeeping per game, stored in the scores SQLite table."""

from __future__ import annotations

from pathlib import Path

from .db import Db
from .schema import SCORES_TABLE


class SqliteScoreService:
    def __init__(self, db_path: Path) -> None:
        self._db = Db(db_path)

    def get_best(self, game_id: str) -> int:
        row = self._db.query_one(f"SELECT score FROM {SCORES_TABLE} WHERE game_id = ?", (game_id,))
        return int(row["score"]) if row else 0

    def submit(self, game_id: str, score: int) -> int:
        best = max(self.get_best(game_id), score)
        self._db.execute(
            f"INSERT INTO {SCORES_TABLE} (game_id, score) VALUES (?, ?) "
            f"ON CONFLICT(game_id) DO UPDATE SET score = excluded.score",
            (game_id, best))
        return best
