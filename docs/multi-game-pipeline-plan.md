# Multi-Game Pipeline — Implementation Plan

Goal: evolve the 3D Snake codebase into a pipeline that can host additional games,
keeping the existing invariants (pure, I/O-free game cores; service contracts;
single authoritative server-side loop; thin REST transport; MVVM frontend).

Each phase is independently shippable. Work top-down; check off todos as they land.

---

## Phase 0 — Baseline hygiene

- [ ] Add a shared **contract test suite** (`tests/contracts/`) that any `Game`
      implementation must pass (state round-trip, tick determinism with seeded RNG,
      action validation, terminal-state handling). Port the relevant assertions
      from the existing snake tests as the first implementation.
- [ ] Add CI (GitHub Actions) running `python -m pytest tests/ -q` on every PR so
      each phase below is gated.
- [ ] Pin `requirements.txt` versions (or add `requirements-lock.txt`) so the
      pipeline baseline is reproducible.
- [ ] Document the invariants in `CONTRIBUTING.md`: pure core, no I/O in `games/`,
      one stepper per session, contracts over implementations.

## Phase 1 — Game registry and generic routes

- [ ] Introduce the generic `Game` protocol in `snake/contracts.py` (or a new
      `snake/engine.py`): `init(config) -> GameState`, `state()`,
      `apply_action(player, action)`, `tick() -> GameState`.
- [ ] Make `InMemoryGameService` implement the `Game` protocol without changing
      its public snake behavior (adapter or rename + alias).
- [ ] Create `snake/games/__init__.py` with a registry: `register(game_id, factory)`,
      `get(game_id)`, `list_games()`; register `"snake"` as the first entry.
- [ ] Generalize routes in `snake/app.py` to `/api/games/{game_id}/state`,
      `/api/games/{game_id}/new`, `/api/games/{game_id}/action`, plus
      `GET /api/games` listing available games. Keep the legacy `/api/*` routes
      as thin redirects during migration.
- [ ] Generalize `LeaderboardService` to `submit(user_id, game_id, mode, score)`
      and `top(game_id, mode, limit)`; migrate `leaderboard.json` with a versioned
      read/write (backfill old single/multi boards under `game_id="snake"`).
- [ ] Update `schemas.py` with per-game request/response envelopes:
      `{gameId, state, players, status, ...}`.
- [ ] Port `tests/test_api.py` to the generic routes; add registry tests.

## Phase 2 — Session-scoped game instances (kill the singletons)

- [ ] Introduce `GameSession`: owns one game instance + one loop + (user_id, mode)
      context, keyed by a session id stored in the user cookie or returned by
      `/new`.
- [ ] Change `GameLoop` to be constructed per session instead of living once on
      `app.state`; remove the mutable `set_context` race by passing context at
      construction.
- [ ] Add a `SessionService` contract (in-memory impl first, JSON-file or DB
      later) managing session lifecycle: create, resolve from request, expire
      idle sessions (e.g. after 30 min).
- [ ] Update `dependencies.py` providers to resolve the session from the
      request instead of global `app.state` singletons.
- [ ] Tests: two concurrent sessions advance independently; session expiry
      stops its loop; loop task is cancelled on session close.
- [ ] Verify no shared mutable state remains between sessions (audit
      `GameLoop._user_id/_mode`, global settings).

## Phase 3 — Serialization out of the domain

- [ ] Define a `Serializable` protocol (`to_dict()`) implemented by DTO classes,
      not by domain models.
- [ ] Create `snake/games/snake/dto.py` with `SnakeStateDTO.from_state(state)`;
      remove `GameState.to_dict()` (or keep it temporarily as a deprecated shim).
- [ ] Standardize the wire envelope in `schemas.py` so the frontend shell can
      render any game: `{gameId, status, players: [...], state: {...}, meta}`.
- [ ] Update `static/api.js`/`viewmodel.js` to consume the envelope and dispatch
      on `gameId`.
- [ ] Tests: DTO round-trip equals old `to_dict()` output for snake (golden
      fixture) so the frontend migration is safe.

## Phase 4 — Pluggable rules and effects

- [ ] Replace the imperative `_apply_fruit` branches with an effect registry:
      `effects.register(FruitKind.APPLE, handler(state, player))` in
      `snake/games/snake/effects.py`.
- [ ] Move `FRUIT_KIND_WEIGHTS`, `FRUIT_DURATION_S`, grid resize bounds, and
      star duration into a per-game config dataclass loaded from
      `snake/games/snake/config.py` (or JSON), injected into the game service.
- [ ] Extract spawn logic (`_spawn_snake`, `_spawn_fruit`, `_free_cells`) into
      a `Board`/`Spawner` helper so new games can reuse grid occupancy utilities.
- [ ] Tests: register a dummy effect in tests and assert it fires; config
      override changes fruit weights deterministically with a seeded RNG.

## Phase 5 — Per-user settings and identity hardening

- [ ] Key `SettingsService` by `user_id` (`get(user_id)`, `set(user_id, ...)`);
      keep a global default for anonymous users; migrate `settings.json`.
- [ ] Add settings to the session context so each user's speed/torus follow
      them across sessions.
- [ ] Tests: two users get independent settings; anonymous fallback works.

## Phase 6 — Frontend game shell

- [ ] Turn `static/main.js` into a composition root that loads a game module by
      id: `games/<id>/{scene.js, view.js, input.js, hud.js}` behind a shared
      `GameView` interface (`render(envelope)`, `onInput(action)`).
- [ ] Keep snake's current modules as `games/snake/*` unchanged in behavior.
- [ ] Add a minimal game picker on `index.html` fed by `GET /api/games`.
- [ ] Smoke-test in browser: snake renders and plays exactly as before.

## Phase 7 — Transport adapter (preparation for real-time games)

- [ ] Define a `Transport` protocol behind `api.js`: `poll()` vs `subscribe()`.
- [ ] Implement the WebSocket adapter (`/ws/games/{game_id}`) server-side,
      pushing state deltas after each tick; keep REST polling as the fallback.
- [ ] Frontend: `viewmodel.js` subscribes when the game advertises
      `realTime: true` in `/api/games`, else polls.
- [ ] Tests: integration test driving a game over WebSocket (use FastAPI
      TestClient websocket support).

## Phase 8 — Second game as pipeline proof (e.g. a grid-based game)

- [ ] Scaffold `snake/games/<new-game>/` with pure core + config + effects +
      DTO, registered in the registry.
- [ ] Implement its `Game` core and pass the shared contract test suite from
      Phase 0.
- [ ] Add its frontend module under `static/games/<new-game>/`.
- [ ] Leaderboard entries appear under the new `game_id` automatically.
- [ ] End-to-end test: create session, play a few ticks via API, score lands on
      the correct board.

---

## Cross-cutting Definition of Done (every phase)

- [ ] `python -m pytest tests/ -q` green.
- [ ] No new global mutable state introduced.
- [ ] New code depends only on contracts/protocols, not concrete implementations.
- [ ] README architecture section updated to reflect the change.
