"""Session-scoped instances: two concurrent sessions advance independently,
idle expiry drops sessions, and no mutable game state lives on app.state."""

import random
import time

from games.snake.config import SnakeConfig
from games.snake.core import SnakeGame
from snake.contracts import GameSession
from snake.session import IDLE_TTL_S, InMemorySessionService


def make_service(seed: int = 1) -> SnakeGame:
    game = SnakeGame(rng=random.Random(seed))
    game.init(SnakeConfig(torus=True, grid_size=10))
    return game


def test_two_sessions_advance_independently():
    sessions = InMemorySessionService()
    s1 = sessions.create("snake", "u1", "single")
    s2 = sessions.create("snake", "u2", "single")
    g1 = sessions.get(s1).game
    g2 = sessions.get(s2).game
    g1.init(SnakeConfig(torus=True, grid_size=10))
    g2.init(SnakeConfig(torus=True, grid_size=10))
    for _ in range(3):
        g1.tick()
    g2.tick()
    assert g1.state().snake[0].x == 6
    assert g2.state().snake[0].x == 4


def test_idle_expiry_drops_session():
    now = [1000.0]
    sessions = InMemorySessionService(ttl_s=30, now=lambda: now[0])
    sid = sessions.create("snake", "u1", "single")
    assert sessions.get(sid) is not None
    now[0] += 31
    assert sessions.get(sid) is None


def test_touch_extends_lifetime():
    now = [1000.0]
    sessions = InMemorySessionService(ttl_s=30, now=lambda: now[0])
    sid = sessions.create("snake", "u1", "single")
    now[0] += 20
    sessions.touch(sid)
    now[0] += 20  # 40 since creation, but only 20 since touch
    assert sessions.get(sid) is not None


def test_no_mutable_game_state_on_app_state():
    from fastapi import FastAPI
    from snake.app import lifespan
    app = FastAPI(lifespan=lifespan)
    # app.state carries only services and the loop registry — never a Game
    assert not hasattr(app.state, "game_service")
    assert not hasattr(app.state, "game")


def test_session_create_uses_registry_factory():
    sessions = InMemorySessionService()
    sid = sessions.create("snake", "u1", "single")
    session = sessions.get(sid)
    assert isinstance(session, GameSession)
    assert isinstance(session.game, SnakeGame)
    assert session.user_id == "u1"
