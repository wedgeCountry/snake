# 3D Snake (FastAPI)

Echtes 3D-Snake im Browser: 10×10×10-Würfel, Torus-Modus, Wisch-/Pinch-Steuerung.

## Architektur

- **Python core** (`snake/core/`): reine Spiellogik und Modelle — vollständig
  per pytest testbar, kein I/O.
- **Service Contracts Pattern**: Konsumenten hängen nur von `GameService`,
  `ScoreService`, `SettingsService` (Protocols in `contracts.py`) ab; konkrete
  Implementierungen (`core/game.py`, `services/score.py`, `services/settings.py`)
  werden in `dependencies.py` als Provider auf `app.state` gelegt (in Tests
  direkt auf `app.state` überschreibbar).
- **Server-seitige Game-Loop** (`snake/loop.py`): eine asyncio-Task steppt das
  Spiel im `step_time_ms`-Takt, sobald ein Spiel aktiv ist (`/api/new`). Sie ist
  der einzige Stepper und reicht bei Game Over den Score beim `ScoreService` ein.
  Richtungswechsel laufen über eine serverseitige Queue (`set_direction`), die
  pro Schritt genau eine Richtung anwendet.
- **FastAPI** (`snake/app.py`): dünne REST-Schicht, Request-Schemas in
  `snake/schemas.py`. Endpunkte: `/api/state`, `/api/new`, `/api/direction`,
  `/api/settings`.
- **Frontend** (`static/`) als MVVM: `api.js` (einziger Backend-Brückenkopf),
  `viewmodel.js` (pollt `/api/state`), `scene.js` (Three.js-Szenenaufbau +
  Kamera), `hud.js` (DOM-Anzeige), `view.js` (reines Rendering),
  `input.js` (Touch-/Tastatur-Gesten), `main.js` (Composition Root).
  Styling in `style.css`.

## Start

```bash
pip install -r requirements.txt
uvicorn snake.app:app --reload
```

Dann http://localhost:8000 öffnen.

## Tests

```bash
python -m pytest tests/ -q
```
