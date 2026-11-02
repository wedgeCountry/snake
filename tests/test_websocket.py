"""Phase 7: integration test driving a game over the WebSocket transport."""

import pytest
from fastapi.testclient import TestClient

from snake.app import app
from snake.contracts import SESSION_COOKIE
from snake.services.leaderboard import JsonFileLeaderboardService
from snake.services.score import JsonFileScoreService
from snake.services.settings import JsonFileSettingsService
from snake.services.user import CookieUserService
from snake.session import InMemorySessionService


@pytest.fixture()
def client(tmp_path):
    app.state.session_service = InMemorySessionService()
    app.state.score_service = JsonFileScoreService(tmp_path / "scores.json")
    app.state.settings_service = JsonFileSettingsService(tmp_path / "settings.json")
    app.state.user_service = CookieUserService()
    app.state.leaderboard_service = JsonFileLeaderboardService(tmp_path / "leaderboard.json")
    app.state.session_loops = {}
    with TestClient(app) as c:
        yield c


def test_websocket_pushes_envelopes(client):
    client.post("/api/settings", json={"step_time_ms": 60})
    r = client.post("/api/games/snake/new", json={"torus": True})
    session_id = client.cookies.get(SESSION_COOKIE)
    with client.websocket_connect(f"/ws/games/snake?session={session_id}") as ws:
        first = ws.receive_json()
        second = ws.receive_json()
    assert first["v"] == 1
    assert first["gameId"] == "snake"
    assert first["sessionId"] == session_id
    assert "state" in first and "status" in first
    assert second["state"]["snake"][0] != first["state"]["snake"][0] or second["status"] == first["status"]


def test_websocket_unknown_session_closes(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/games/snake?session=nonexistent") as ws:
            ws.receive_json()
