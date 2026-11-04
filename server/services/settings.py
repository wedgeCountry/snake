"""Per-user settings stored in the settings SQLite table (one row per user).

Platform-wide step-time clamps (the speed slider is generic across games)."""

from __future__ import annotations

from pathlib import Path

from .db import Db

MIN_STEP_MS = 60
MAX_STEP_MS = 400
DEFAULT_STEP_MS = 260

ANONYMOUS_USER_ID = "anonymous"


class SqliteSettingsService:
    """Per-user settings keyed by user_id. The anonymous default is used when
    no user id is known."""

    def __init__(self, db_path: Path) -> None:
        self._db = Db(db_path)

    def _bucket(self, user_id: str) -> str:
        return user_id or ANONYMOUS_USER_ID

    def _row(self, user_id: str) -> tuple[int, bool]:
        row = self._db.query_one(
            "SELECT step_time_ms, torus FROM settings WHERE user_id = ?", (self._bucket(user_id),))
        if row is None:
            return DEFAULT_STEP_MS, True
        return int(row["step_time_ms"]), bool(row["torus"])

    def get(self, user_id: str) -> dict:
        step, torus = self._row(user_id)
        return {"stepTimeMs": step, "torus": torus}

    def set(self, user_id: str, settings: dict) -> dict:
        step, torus = self._row(user_id)
        if "stepTimeMs" in settings:
            step = int(settings["stepTimeMs"])
        if "torus" in settings:
            torus = bool(settings["torus"])
        self._db.execute(
            "INSERT INTO settings (user_id, step_time_ms, torus) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET step_time_ms = excluded.step_time_ms, "
            "torus = excluded.torus",
            (self._bucket(user_id), step, int(torus)))
        return self.get(user_id)

    def get_step_time_ms(self, user_id: str) -> int:
        step, _ = self._row(user_id)
        return int(min(MAX_STEP_MS, max(MIN_STEP_MS, step)))

    def set_step_time_ms(self, user_id: str, value: int) -> int:
        v = int(min(MAX_STEP_MS, max(MIN_STEP_MS, value)))
        self.set(user_id, {"stepTimeMs": v})
        return v

    def get_torus(self, user_id: str) -> bool:
        _, torus = self._row(user_id)
        return torus

    def set_torus(self, user_id: str, enabled: bool) -> bool:
        self.set(user_id, {"torus": bool(enabled)})
        return bool(enabled)
