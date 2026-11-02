from __future__ import annotations

import json
from pathlib import Path

from games.snake.config import DEFAULT_STEP_MS, MAX_STEP_MS, MIN_STEP_MS

ANONYMOUS_USER_ID = "anonymous"


class JsonFileSettingsService:
    """Per-user settings keyed by user_id, persisted to a JSON file.
    The anonymous default is used when no user id is known."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data = self._load()

    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text())
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data))

    def _bucket(self, user_id: str) -> dict:
        return self._data.setdefault(user_id or ANONYMOUS_USER_ID, {})

    def get(self, user_id: str) -> dict:
        return dict(self._bucket(user_id))

    def set(self, user_id: str, settings: dict) -> dict:
        bucket = self._bucket(user_id)
        bucket.update(settings)
        self._save()
        return dict(bucket)

    def get_step_time_ms(self, user_id: str) -> int:
        v = self._bucket(user_id).get("stepTimeMs", DEFAULT_STEP_MS)
        return int(min(MAX_STEP_MS, max(MIN_STEP_MS, v)))

    def set_step_time_ms(self, user_id: str, value: int) -> int:
        v = int(min(MAX_STEP_MS, max(MIN_STEP_MS, value)))
        self.set(user_id, {"stepTimeMs": v})
        return v

    def get_torus(self, user_id: str) -> bool:
        return bool(self._bucket(user_id).get("torus", True))

    def set_torus(self, user_id: str, enabled: bool) -> bool:
        self.set(user_id, {"torus": bool(enabled)})
        return bool(enabled)
