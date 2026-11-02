from __future__ import annotations

import json
from pathlib import Path


class JsonFileScoreService:
    """Best-score bookkeeping per game, persisted to a JSON file, cached in memory."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._best = self._read()

    def _read(self) -> dict[str, int]:
        try:
            data = json.loads(self._path.read_text())
            return {str(k): int(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (OSError, ValueError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._best))

    def get_best(self, game_id: str) -> int:
        return self._best.get(game_id, 0)

    def submit(self, game_id: str, score: int) -> int:
        best = max(self._best.get(game_id, 0), score)
        self._best[game_id] = best
        self._save()
        return best
