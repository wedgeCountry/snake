"""SQLite storage layer: one database file holds all persistent tables.

All services share a single connection guarded by a lock (FastAPI sync
endpoints run in a threadpool, so the connection must allow cross-thread
use). The schema is created idempotently on connect.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS scores (
    game_id TEXT PRIMARY KEY,
    score   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    user_id      TEXT PRIMARY KEY,
    step_time_ms INTEGER NOT NULL DEFAULT 260,
    torus        INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS leaderboard (
    player_id TEXT NOT NULL,
    game_id   TEXT NOT NULL,
    mode      TEXT NOT NULL,
    score     INTEGER NOT NULL,
    PRIMARY KEY (player_id, game_id, mode)
);
CREATE TABLE IF NOT EXISTS savegames (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    game_id    TEXT NOT NULL,
    mode       TEXT NOT NULL DEFAULT 'single',
    name       TEXT NOT NULL DEFAULT '',
    state      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_savegames_user_game ON savegames (user_id, game_id);
CREATE INDEX IF NOT EXISTS idx_leaderboard_board ON leaderboard (game_id, mode, score DESC);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (and create) the database at db_path with the full schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


class Db:
    """Shared connection + lock wrapper used by all SQLite services."""

    def __init__(self, db_path: Path) -> None:
        self.conn = connect(db_path)
        self.lock = threading.Lock()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute(sql, params).fetchone()
