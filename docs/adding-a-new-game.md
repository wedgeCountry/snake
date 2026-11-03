# Adding a new game — minimal guide

A new game is **one Python package + one registration line + one JS view module**.
The contract suite picks it up automatically. No changes to `server/app.py`, routes,
or the frontend shell are needed.

## Before you start

Read `CONTRIBUTING.md` (definition of done) and skim `games/collector/` — it is the
smallest working example. Rules of the pipeline:

- **Pure core**: no I/O, no FastAPI, no globals; take `rng: random.Random | None`.
- **One stepper**: implement `tick()`; the server's `SessionLoop` calls it. Clients
  only send actions via `apply_action(player, action)`.
- **Serialization belongs to a DTO/serialize function**, registered with the game —
  never `to_dict()` on your domain model.

## Steps

1. **Create `games/<id>/`** with `__init__.py`, `core.py`, `config.py`:

   ```python
   # games/tictactoe/__init__.py
   from ..registry import register
   from .core import TttGame, serialize

   register("tictactoe", name="Tic-Tac-Toe", real_time=False, max_players=2,
            factory=lambda rng: TttGame(rng=rng), serialize=serialize)
   # optional: map per-user settings + new-game request to your config dataclass,
   # so the generic routes never import your game (default honors stepTimeMs only)
   # register(..., build_config=lambda settings, mode, torus: TttConfig(...))
   ```

   Leaderboard, best-score and user identity are already generic: scores land on
   the per-game leaderboard automatically when the session ends, and the caller's
   cross-game profile is served at `GET /api/users/me/stats`; the envelope's
   `meta.userBest` carries the player's own best for the current game/mode.

   ```python
   # games/tictactoe/core.py (sketch — the Game protocol is in games/engine.py)
   class TttGame:
       def init(self, config): ...          # -> state
       def state(self): ...                 # -> state
       def apply_action(self, player, action): ...  # validate, raise ValueError on garbage
       def tick(self): ...                  # advance one step, set status "won"/"dead"
       def max_players(self): return 2
       def is_terminal(self): return self.state().status != "running"
       @property
       def state_schema_version(self): return 1

   def serialize(state) -> dict: ...        # wire format for the envelope's `state`
   ```

2. **Register the package** in `games/__init__.py`: `from . import tictactoe`.
3. **Frontend**: add `static/games/tictactoe/view.js` exposing
   `window.GameView_tictactoe` with `render(vm, now)`, `updateHud(vm)`,
   `showOverlay(title, msg, cta)`, `dispose()`. It appears in the game-select menu
   automatically via `GET /api/games`.
4. **Tests**: add `tests/test_<id>.py`. The shared suite in `tests/contracts/`
   (state round-trip, seeded-RNG determinism, action validation, terminal
   stability) already runs against your game because it is parametrized over
   the registry.

## Verify

```bash
python -m pytest tests/ -q     # contract suite now includes your game
node static/tests/run.js
curl localhost:8000/api/games   # your game is listed
```

Routes available immediately, session-scoped, no singleton state:
`POST /api/games/<id>/new`, `GET /api/games/<id>/state`,
`POST /api/games/<id>/action`, `WS /ws/games/<id>?session=...`,
`GET /api/leaderboard/<id>/<mode>`.
