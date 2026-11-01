from __future__ import annotations

import json
from pathlib import Path

from ..core.game import DEFAULT_STEP_MS, MAX_STEP_MS, MIN_STEP_MS


class JsonFileSettingsService:
    """User settings persisted to a JSON file, cached in memory (write-through)."""

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

    def get_step_time_ms(self) -> int:
        v = self._data.get("stepTimeMs", DEFAULT_STEP_MS)
        return int(min(MAX_STEP_MS, max(MIN_STEP_MS, v)))

    def set_step_time_ms(self, value: int) -> int:
        v = int(min(MAX_STEP_MS, max(MIN_STEP_MS, value)))
        self._data["stepTimeMs"] = v
        self._save()
        return v

    def get_torus(self) -> bool:
        return bool(self._data.get("torus", True))

    def set_torus(self, enabled: bool) -> bool:
        self._data["torus"] = bool(enabled)
        self._save()
        return bool(enabled)
