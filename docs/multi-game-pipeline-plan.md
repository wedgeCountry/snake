# Multi-Game Pipeline — Implementation Plan (v2, prototyping)

Goal: evolve the 3D Snake codebase into a pipeline that can host additional games.

**Prototyping stance:** no players yet, no backward compatibility. Legacy routes,
old JSON stores, and the old wire format may be deleted or broken outright — do
not write migration shims, redirects, or golden fixtures for the old formats.
What must be right *now* is the set of **patterns and contracts**, so the system
can be refactored later without rewrites.

## Refactorability principles (the non-negotiables)

- [x] **Pure cores:** game logic lives in `games/<id>/` with zero I/O and an
      injectable RNG; fully testable with pytest.
- [x] **Contracts over implementations:** everything consumers touch is a
      `Protocol` (engine, session, persistence, settings, transport, view);
      concrete impls are swappable without touching consumers.
- [x] **One authoritative stepper per session:** clients only submit actions and
      read state; the server owns all state transitions.
- [x] **No global mutable game state:** one game instance per session, never on
      `app.state` as a singleton.
- [x] **Versioned wire envelope** (`{v, gameId, ...}`) so the frontend shell and
      future clients can evolve independently of individual games.
- [x] **Shared contract test suite** every `Game` implementation must pass.

---

## Phase 0 — Contracts first (define the seams before the code)

Define all protocols and the contract test suite in one pass, with snake as the
reference implementation:

- [x] `Game` protocol (in `games/engine.py`): `init(config) -> GameState`,
      `state()`, `apply_action(player, action)`, `tick() -> GameState`,
      plus `max_players()`, `is_terminal()`, and a versioned state schema
      (`state_schema_version`) for future replay/migration.
- [x] Abstract `GameState` base (serialization via DTOs, not `to_dict()` on the
      domain model — the `Serializable` protocol belongs to DTO classes).
- [x] `SessionService`, `ScoreService`, `LeaderboardService` (keyed by
      `game_id`), `SettingsService` (keyed by `user_id`), `Transport` protocols.
- [x] Shared contract test suite in `tests/contracts/`: state round-trip, tick
      determinism with seeded RNG, action validation, terminal-state handling.
      Port existing snake test assertions as the first implementation.
- [x] CI (GitHub Actions) running `python -m pytest tests/ -q` on every PR.
- [x] Pin dependency versions for a reproducible baseline.
- [x] `CONTRIBUTING.md` documenting the principles above as the definition of
      "done" for any new game.

## Phase 1 — Registry, generic routes, top-level `games/` package

- [x] Move the game code to a top-level `games/` package: `games/snake/` is the
      first entry (pure core + config + effects + dto). Delete the old
      `snake/core/game.py` path; no aliases.
- [x] `games/registry.py`: `register(game_id, factory)`, `get(game_id)`,
      `list_games()` (each entry advertises `{id, name, realTime, maxPlayers}`).
- [x] Generic routes in `server/app.py`: `GET /api/games`,
      `/api/games/{game_id}/new`, `/api/games/{game_id}/state`,
      `/api/games/{game_id}/action`. Delete the legacy `/api/*` routes outright.
- [x] Generic envelope in `schemas.py`: `{v: 1, gameId, status, players, state,
      meta}`; snake's DTO produces `state`.
- [x] Port `tests/test_api.py` to the generic routes; add registry tests.

## Phase 2 — Session-scoped instances (kill the singletons)

- [x] `GameSession`: one game instance + one loop + (user_id, mode) context,
      keyed by a session id (cookie or returned by `/new`).
- [x] Construct `GameLoop` per session; remove `set_context` by passing context
      at construction. Note for the future: a session owns a live asyncio task,
      so any future multi-process/DB-backed session store needs a loop
      claim/lease strategy — keep the `SessionService` interface shaped for it.
- [x] `SessionService` in-memory impl with idle expiry (e.g. 30 min); interface
      allows a shared store later.
- [x] Providers in `dependencies.py` resolve the session from the request.
- [x] Tests: two concurrent sessions advance independently; expiry cancels the
      loop; audit that no mutable game state remains on `app.state`.

## Phase 3 — DTO layer and frontend envelope

- [x] `games/snake/dto.py` with `SnakeStateDTO.from_state(state)`; remove
      `GameState.to_dict()` — the wire format is free to change, no golden
      fixtures against the old one.
- [x] Frontend: `static/api.js`/`viewmodel.js` consume the versioned envelope
      and dispatch on `gameId`.

## Phase 4 — Generic rules/effects contract (pipeline-level, not snake-only)

- [x] Define the pipeline-wide rule contract: games register effects/handlers
      (`register(kind, handler)`) and declare weights/durations in a config
      dataclass — this is the *generic* pattern every game follows, not a
      snake-specific one.
- [x] Snake's `games/snake/effects.py` + `config.py` as the reference
      implementation; extract shared grid-occupancy/spawn helpers into
      `games/common/board.py`.
- [x] Tests: contract suite covers effect registration; seeded-RNG test proves
      config overrides are deterministic.

## Phase 5 — Per-user settings

- [x] `SettingsService` keyed by `user_id` with an anonymous default
      (`settings.json` may be reset — no migration needed).
- [x] Tests: independent settings per user; anonymous fallback.

## Phase 6 — Frontend game shell

- [x] `static/main.js` as composition root loading `static/games/<id>/` modules
      (`scene.js`, `view.js`, `input.js`, `hud.js`) behind a designed `GameView`
      interface: `render(envelope)`, `onInput(action)`, `dispose()`, with
      per-game asset namespacing and an error boundary so one game's throw
      cannot kill the shell.
- [x] Snake's modules move to `static/games/snake/` unchanged in behavior.
- [x] Game picker on `index.html` fed by `GET /api/games`.
- [x] JS-side contract tests for `GameView` (not just a manual smoke test).

## Phase 7 — Transport adapter (real-time seam)

- [x] `Transport` protocol behind `api.js`: `poll()` vs `subscribe()`.
- [x] WebSocket route `/ws/games/{game_id}` pushing state after each tick;
      REST polling remains the fallback; games advertise `realTime` in the
      registry.
- [x] `viewmodel.js` subscribes when `realTime` is set, else polls.
- [x] Integration test driving a game over WebSocket.

## Phase 8 — Second game as pipeline proof

- [x] Scaffold `games/<new-game>/` (core + config + effects + dto) registered
      in the registry; passes the shared contract suite from Phase 0.
- [x] Frontend module under `static/games/<new-game>/`.
- [x] End-to-end test: new session, play ticks via API, score lands on the
      correct per-game leaderboard.

---

## Definition of Done (every phase)

- [x] `python -m pytest tests/ -q` green (plus JS contract tests from Phase 6).
- [x] No new global mutable state; consumers depend only on protocols.
- [x] New game logic contains no I/O.
- [x] README architecture section updated.
