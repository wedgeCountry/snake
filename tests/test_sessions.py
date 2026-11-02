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


def test_expiry_cancels_and_removes_session_loop():
    import asyncio
    from snake.session import SessionLoop
    from snake.services.score import JsonFileScoreService
    import tempfile, pathlib
    now = [1000.0]
    removed = []
    sessions = InMemorySessionService(ttl_s=30, now=lambda: now[0],
                                      on_expire=lambda sid: removed.append(sid))
    sid = sessions.create("snake", "u1", "single")
    session = sessions.get(sid)
    session.game.state().step_time_ms = 5
    loops = {}
    loop = SessionLoop(session, JsonFileScoreService(pathlib.Path(tempfile.mkdtemp()) / "s.json"))
    loops[sid] = loop
    session.game.state().status = "running"

    async def run():
        await loop.start()
        await asyncio.sleep(0.05)
        assert loop.running
        now[0] += 31
        sessions.get("other")  # triggers expiry sweep
        assert sessions.get(sid) is None
        assert removed == [sid]
        await loop.stop()
        assert not loop.running

    asyncio.run(run())


def test_loop_removes_itself_on_natural_termination():
    import asyncio
    from snake.session import SessionLoop
    from snake.services.score import JsonFileScoreService
    import tempfile, pathlib
    from games.snake.models import Cell, Direction
    game = make_service()
    state = game.state()
    state.snake = [Cell(4, 2, 2), Cell(3, 2, 2), Cell(2, 2, 2)]
    state.direction = Direction(1, 0, 0)
    state.food = Cell(0, 0, 0)
    state.step_time_ms = 5
    from games.snake.config import SnakeConfig
    game._config = SnakeConfig(torus=False, grid_size=5)
    state.torus = False
    finished = []
    sessions = InMemorySessionService()
    sid = sessions.create("snake", "u1", "single")
    session = sessions.get(sid)
    session.game = game
    loop = SessionLoop(session, JsonFileScoreService(pathlib.Path(tempfile.mkdtemp()) / "s.json"),
                       on_finished=lambda: finished.append(True))

    async def run():
        await loop.start()
        for _ in range(50):
            await asyncio.sleep(0.01)
            if not loop.running:
                break

    asyncio.run(run())
    assert game.state().status == "dead"
    assert finished == [True]
    assert not loop.running
