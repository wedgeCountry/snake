# 3D Snake (FastAPI)

Echtes 3D-Snake im Browser: 10×10×10-Würfel, Torus-Modus, Wisch-/Pinch-Steuerung.

## Architektur

- **Python core** (`snake/`): Spiellogik, Modelle und Service-Verträge
  (`contracts.py`, Protocols) — vollständig per pytest testbar, kein I/O.
- **Service Contracts Pattern**: Konsumenten hängen nur von `GameService`,
  `ScoreService`, `SettingsService` (Protocols) ab; konkrete Implementierungen
  werden in `dependencies.py` per DI injiziert (in Tests überschreibbar).
- **Server-seitige Game-Loop** (`snake/loop.py`): eine asyncio-Task steppt das
  Spiel im `step_time_ms`-Takt, sobald ein Spiel aktiv ist (`/api/new`). Bei
  Game Over reicht sie den Score beim `ScoreService` ein. Richtungswechsel
  laufen über eine serverseitige Queue (`set_direction`), die pro Schritt
  genau eine Richtung anwendet.
- **FastAPI** (`snake/app.py`): REST-Endpunkte `/api/state`, `/api/new`,
  `/api/direction`, `/api/step`, `/api/gameover`, `/api/settings`.
- **Frontend** (`static/`) als MVVM: `api.js` (einziger Backend-Brückenkopf),
  `viewmodel.js` (pollt `/api/state`, Interpolation, Input-Mapping),
  `view.js` (Three.js-Rendering + DOM), `main.js` (Composition Root +
  Input-Events). Styling in `style.css`.

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
