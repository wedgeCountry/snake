"""SQLite storage layer: one database file holds all persistent tables.

The table definitions live exclusively in schema.py (the single source of
truth); this module only opens the database and applies that schema. All
services share a single connection guarded by a lock (FastAPI sync endpoints
run in a threadpool, so the connection must allow cross-thread use).
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .schema import create_schema


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (and create) the database at db_path with the full schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    create_schema(conn)
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
