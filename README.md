# Game Platform (3D Snake + mehr)

Multi-Game-Pipeline im Browser: Snake (3D, 10×10×10-Würfel, Torus-Modus) und
Collector (2D) laufen über dieselben generischen Routen und Verträge.

## Architektur

- **Reine Kerne** (`games/<id>/`): Spiellogik ohne I/O, mit injizierbarem RNG,
  voll per pytest testbar. Snake: `games/snake/` (core + config + effects +
  dto), Collector: `games/collector/`.
- **Contracts over implementations**: Konsumenten hängen nur von Protocols ab
  (`games/engine.py`: `Game`, `Serializable`; `server/contracts.py`:
  `SessionService`, `ScoreService` (keyed by `game_id`),
  `LeaderboardService` (keyed by `game_id`), `SettingsService` (keyed by
  `user_id`), `Transport`).
- **Registry** (`games/registry.py`): `register`/`get`/`list_games`; jede
  registration advertised `{id, name, realTime, maxPlayers}`.
- **Session-Scoped Instances** (`server/session.py`): ein `Game` + ein
  `SessionLoop` (asyncio-Task) pro Session, In-Memory-`SessionService` mit
  Idle-Expiry (30 min). Kein globaler mutable Game-State auf `app.state`.
- **Generische Routen** (`server/app.py`): `GET /api/games`,
  `POST /api/games/{game_id}/new`, `GET /api/games/{game_id}/state`,
  `POST /api/games/{game_id}/action`, plus WebSocket `/ws/games/{game_id}`
  (Real-Time-Transport; REST-Polling als Fallback, Push-only — der
  Session-Loop ist der einzige Stepper). Versionierter Envelope:
  `{v, gameId, sessionId, status, players, state, meta}`; Session-Metadaten
  (best/userId/leaderboard) liegen in `meta`, nicht im Game-State.
- **DTO-Layer**: Serialisierung gehört zu DTO-Klassen
  (`games/snake/dto.py`), nicht zum Domain-Modell; pro Spiel registriert
  (`serialize` im Registry-Eintrag), sodass `app.py` spiel-agnostisch bleibt.
- **Shared Contract Suite** (`tests/contracts/`): parametrisiert über die
  Registry — jede `Game`-Implementierung muss sie bestehen.
- **Frontend-Shell** (`static/main.js` als Composition Root): Game-Picker
  (füttert sich aus `GET /api/games`), lädt `static/games/<id>/` hinter dem
  `GameView`-Interface (`render`/`updateHud`/`showOverlay`/`dispose`) mit
  Error Boundary. `viewmodel.js` konsumiert den Envelope und dispatcht auf
  `gameId`; subscribed bei `realTime`, sonst Polling.

## Start

```bash
pip install -r requirements.txt
uvicorn server.app:app --reload
```

Dann http://localhost:8000 öffnen.

## Tests

```bash
python -m pytest tests/ -q   # inkl. tests/contracts/
node static/tests/run.js     # JS GameView Contract-Tests
```

GUI-Test (headless Chromium via Playwright: klickt Start, waehlt Snake im
Game-Picker und drueckt dann jede Schaltflaeche einmal der Reihe nach):

```bash
pip install -r requirements.txt -r requirements-gui.txt
python -m playwright install chromium
python -m pytest tests/test_gui.py -q
```
