"""Phase 7: integration tests driving a game over the WebSocket transport,
including the single-stepper guarantee (WS pushes, never ticks)."""

import time

import pytest
from fastapi.testclient import TestClient

from server.app import app
from server.contracts import SESSION_COOKIE
from server.services.leaderboard import JsonFileLeaderboardService
from server.services.score import JsonFileScoreService
from server.services.settings import JsonFileSettingsService
from server.services.user import CookieUserService
from server.session import InMemorySessionService


@pytest.fixture()
def client(tmp_path):
    app.state.session_loops = {}
    app.state.session_service = InMemorySessionService()
    app.state.score_service = JsonFileScoreService(tmp_path / "scores.json")
    app.state.settings_service = JsonFileSettingsService(tmp_path / "settings.json")
    app.state.user_service = CookieUserService()
    app.state.leaderboard_service = JsonFileLeaderboardService(tmp_path / "leaderboard.json")
    with TestClient(app) as c:
        yield c


def test_websocket_pushes_envelopes(client):
    client.post("/api/settings", json={"step_time_ms": 60})
    client.post("/api/games/snake/new", json={"torus": True})
    session_id = client.cookies.get(SESSION_COOKIE)
    with client.websocket_connect(f"/ws/games/snake?session={session_id}") as ws:
        first = ws.receive_json()
        second = ws.receive_json()
    assert first["v"] == 1
    assert first["gameId"] == "snake"
    assert first["sessionId"] == session_id
    assert "state" in first and "status" in first
    assert "meta" in first and isinstance(first["meta"], dict)
    assert second["state"]["snake"][0] != first["state"]["snake"][0]


def test_websocket_is_push_only_single_stepper(client):
    """With the background loop stopped, WS must not advance the game."""
    client.post("/api/settings", json={"step_time_ms": 60})
    client.post("/api/games/snake/new", json={"torus": True})
    session_id = client.cookies.get(SESSION_COOKIE)
    loop = app.state.session_loops[session_id]
    client.portal.call(loop.stop)
    with client.websocket_connect(f"/ws/games/snake?session={session_id}") as ws:
        heads = {ws.receive_json()["state"]["snake"][0]["x"] for _ in range(5)}
    assert len(heads) == 1, f"WS handler ticked the game: {heads}"


def test_background_loop_is_single_stepper(client):
    """With no WS client, the background loop advances at its own cadence only."""
    client.post("/api/settings", json={"step_time_ms": 100})
    client.post("/api/games/snake/new", json={"torus": True})
    head0 = client.get("/api/games/snake/state").json()["state"]["snake"][0]
    time.sleep(0.45)
    head1 = client.get("/api/games/snake/state").json()["state"]["snake"][0]
    dist = (head1["x"] - head0["x"]) % 10
    assert 3 <= dist <= 6, f"expected ~4 ticks at 100ms, saw {dist} (double- or under-stepping?)"


def test_websocket_unknown_session_closes(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/games/snake?session=nonexistent") as ws:
            ws.receive_json()
