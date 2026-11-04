"""Single source of truth for the SQLite schema.

Every table and index definition lives in this one module, visible together
in TABLES / INDEXES. `create_schema()` applies them to a connection (used by
db.py to initialize the database), and the services import the table-name
constants from here (e.g. SAVEGAMES_TABLE) so queries can never drift away
from the definitions.
"""

from __future__ import annotations

import sqlite3

# table-name constants referenced by the services' SQL
SCORES_TABLE = "scores"
SETTINGS_TABLE = "settings"
LEADERBOARD_TABLE = "leaderboard"
SAVEGAMES_TABLE = "savegames"

# every table definition, in one place (keyed by the same constants)
TABLES: dict[str, str] = {
    SCORES_TABLE: f"""
        CREATE TABLE IF NOT EXISTS {SCORES_TABLE} (
            game_id TEXT PRIMARY KEY,
            score   INTEGER NOT NULL
        )""",
    SETTINGS_TABLE: f"""
        CREATE TABLE IF NOT EXISTS {SETTINGS_TABLE} (
            user_id      TEXT PRIMARY KEY,
            step_time_ms INTEGER NOT NULL DEFAULT 260,
            torus        INTEGER NOT NULL DEFAULT 1
        )""",
    LEADERBOARD_TABLE: f"""
        CREATE TABLE IF NOT EXISTS {LEADERBOARD_TABLE} (
            player_id TEXT NOT NULL,
            game_id   TEXT NOT NULL,
            mode      TEXT NOT NULL,
            score     INTEGER NOT NULL,
            PRIMARY KEY (player_id, game_id, mode)
        )""",
    SAVEGAMES_TABLE: f"""
        CREATE TABLE IF NOT EXISTS {SAVEGAMES_TABLE} (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT NOT NULL,
            game_id    TEXT NOT NULL,
            mode       TEXT NOT NULL DEFAULT 'single',
            name       TEXT NOT NULL DEFAULT '',
            state      TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )""",
}

INDEXES: list[str] = [
    f"CREATE INDEX IF NOT EXISTS idx_savegames_user_game ON {SAVEGAMES_TABLE} (user_id, game_id)",
    f"CREATE INDEX IF NOT EXISTS idx_leaderboard_board ON {LEADERBOARD_TABLE} (game_id, mode, score DESC)",
]

SCHEMA = ";\n".join(list(TABLES.values()) + INDEXES) + ";"


def create_schema(conn: sqlite3.Connection) -> None:
    """Apply the full schema (idempotent) to an open connection."""
    conn.executescript(SCHEMA)
