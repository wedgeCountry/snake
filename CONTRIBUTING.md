# Contributing — Definition of Done for any new game

The multi-game pipeline is defined by these non-negotiables (see
`docs/multi-game-pipeline-plan.md`):

1. **Pure cores.** Game logic lives in `games/<id>/` with zero I/O and an
   injectable RNG; fully testable with pytest.
2. **Contracts over implementations.** Everything consumers touch is a
   `Protocol` (engine, session, persistence, settings, transport, view).
   Concrete impls are swappable without touching consumers.
3. **One authoritative stepper per session.** Clients only submit actions and
   read state; the server owns all state transitions.
4. **No global mutable game state.** One game instance per session, never on
   `app.state` as a singleton.
5. **Versioned wire envelope** (`{v, gameId, sessionId, status, players,
   state, meta}`) so the frontend shell and future clients evolve
   independently of individual games.
6. **Shared contract test suite.** Every `Game` implementation in the registry
   must pass `tests/contracts/`.

## Adding a game

1. Create `games/<id>/` with `core.py` (implements `games.engine.Game`),
   `config.py` (a `RuleConfig` dataclass declaring effect weights/durations),
   optional `effects.py`, and `dto.py` (DTO classes own serialization).
2. Register it in `games/<id>/__init__.py` via `games.registry.register`.
3. Add a frontend module under `static/games/<id>/` implementing the
   `GameView` interface (`render`, `updateHud`, `showOverlay`, `dispose`).
4. It must pass the shared contract suite automatically (the suite is
   parametrized over the registry) plus your own tests.

## Checks

```bash
python -m pytest tests/ -q   # includes tests/contracts/
node static/tests/run.js     # JS GameView contract tests
```
