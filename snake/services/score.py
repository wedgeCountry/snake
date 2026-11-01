from __future__ import annotations

import json
from pathlib import Path


class JsonFileScoreService:
    """Best-score bookkeeping persisted to a JSON file, cached in memory."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._best = self._read_best()

    def _read_best(self) -> int:
        try:
            return int(json.loads(self._path.read_text()).get("best", 0))
        except (OSError, ValueError, json.JSONDecodeError):
            return 0

    def get_best(self) -> int:
        return self._best

    def submit(self, score: int) -> int:
        self._best = max(self._best, score)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({"best": self._best}))
        return self._best
