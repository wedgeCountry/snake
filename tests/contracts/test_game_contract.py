"""Shared contract suite for any Game implementation.

Covers: state round-trip, tick determinism with seeded RNG, action
validation, terminal-state handling. Every registered game must pass.
"""

from __future__ import annotations

import random

import pytest

from games.engine import Game
from games.registry import _REGISTRY, get


def _make(game_id: str, seed: int = 1) -> Game:
    return get(game_id).factory(random.Random(seed))


@pytest.mark.parametrize("game_id", list(_REGISTRY))
def test_init_returns_state(game_id):
    game = _make(game_id)
    state = game.init(None)
    assert game.state() is not None
    assert not game.is_terminal()
    assert game.max_players() >= 1
    assert isinstance(game.state_schema_version, int)


@pytest.mark.parametrize("game_id", list(_REGISTRY))
def test_tick_determinism_with_seeded_rng(game_id):
    a = _make(game_id, seed=42)
    b = _make(game_id, seed=42)
    a.init(None)
    b.init(None)
    for _ in range(10):
        sa, sb = a.tick(), b.tick()
        if a.is_terminal() and b.is_terminal():
            break
    assert get(game_id).serialize(a.state()) == get(game_id).serialize(b.state())


@pytest.mark.parametrize("game_id", list(_REGISTRY))
def test_action_validation_rejects_garbage(game_id):
    game = _make(game_id)
    game.init(None)
    with pytest.raises((ValueError, KeyError, TypeError)):
        game.apply_action(0, {"direction": "not-a-direction"})


@pytest.mark.parametrize("game_id", list(_REGISTRY))
def test_terminal_state_is_stable(game_id):
    game = _make(game_id)
    game.init(None)
    for _ in range(2000):
        game.tick()
        if game.is_terminal():
            break
    if game.is_terminal():
        before = repr(game.state())
        game.tick()
        assert repr(game.state()) == before


def test_registry_advertises_metadata():
    for info in _REGISTRY.values():
        assert info.id and info.name
        assert isinstance(info.real_time, bool)
        assert info.max_players >= 1
