"""Savegames stored in the savegames SQLite table: one row per save, the
game state as a JSON blob. Scoped per user; a save is only valid for the
game that created it (enforced by the routes)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .db import Db


class SqliteSavegameService:
    def __init__(self, db_path: Path) -> None:
        self._db = Db(db_path)

    @staticmethod
    def _row_to_meta(row) -> dict:
        return {
            "id": int(row["id"]),
            "userId": row["user_id"],
            "gameId": row["game_id"],
            "mode": row["mode"],
            "name": row["name"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def save(self, user_id: str, game_id: str, mode: str, name: str, state: dict[str, Any]) -> dict:
        cur = self._db.execute(
            "INSERT INTO savegames (user_id, game_id, mode, name, state) VALUES (?, ?, ?, ?, ?)",
            (user_id, game_id, mode, name or f"{game_id} save", json.dumps(state)))
        row = self._db.query_one("SELECT * FROM savegames WHERE id = ?", (cur.lastrowid,))
        return self._row_to_meta(row)

    def list(self, user_id: str, game_id: str) -> list[dict]:
        rows = self._db.query(
            "SELECT * FROM savegames WHERE user_id = ? AND game_id = ? ORDER BY id DESC",
            (user_id, game_id))
        return [self._row_to_meta(r) for r in rows]

    def get(self, user_id: str, save_id: int) -> dict | None:
        row = self._db.query_one(
            "SELECT * FROM savegames WHERE id = ? AND user_id = ?", (save_id, user_id))
        if row is None:
            return None
        meta = self._row_to_meta(row)
        meta["state"] = json.loads(row["state"])
        return meta

    def delete(self, user_id: str, save_id: int) -> bool:
        cur = self._db.execute(
            "DELETE FROM savegames WHERE id = ? AND user_id = ?", (save_id, user_id))
        return cur.rowcount > 0
