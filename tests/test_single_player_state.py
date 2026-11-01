"""Tests for GameSinglePlayerState, the single-player wrapper used in tests."""

import random

from snake.models import Cell, Direction, GameSinglePlayerState, GameState
from snake.core.game import InMemoryGameService


def make_state(mode: str = "single", seed: int = 1) -> GameState:
    svc = InMemoryGameService(rng=random.Random(seed))
    return svc.new_game(torus=True, grid_size=10, mode=mode)


def test_wraps_single_player_state():
    state = make_state("single")
    wrapped = GameSinglePlayerState(state)
    assert wrapped.mode == "single"
    assert wrapped.snake == state.snake
    assert wrapped.direction == state.direction
    assert wrapped.score == state.score
    assert wrapped.status == state.status
    assert wrapped.num_players == 1


def test_wraps_multiplayer_state_showing_player_zero():
    state = make_state("multi")
    wrapped = GameSinglePlayerState(state)
    assert wrapped.mode == "single"
    assert wrapped.num_players == 1
    assert wrapped.snake == state.snakes[0]
    assert wrapped.direction == state.directions[0]
    assert wrapped.score == state.scores[0]
    assert wrapped.snakes != state.snakes or len(wrapped.snakes) == 1


def test_wrapper_is_independent_snapshot():
    svc = InMemoryGameService(rng=random.Random(1))
    state = svc.new_game(torus=True, grid_size=10, mode="multi")
    wrapped = GameSinglePlayerState(state)
    svc.step()
    assert wrapped.snake[0] == Cell(2, 5, 5)  # unchanged head
    assert state.snake[0] == Cell(3, 5, 5)  # advanced


def test_wrapper_serializes_single_player_view():
    state = make_state("multi")
    wrapped = GameSinglePlayerState(state)
    d = wrapped.to_dict()
    assert d["mode"] == "single"
    assert len(d["snakes"]) == 1
    assert d["snake"] == d["snakes"][0]
    assert d["score"] == d["scores"][0]
    assert d["direction"] == d["directions"][0]


def test_wrapper_reflects_player_zero_score():
    state = make_state("multi")
    state.scores[0] = 40
    state.scores[1] = 90
    wrapped = GameSinglePlayerState(state)
    assert wrapped.score == 40
    assert wrapped.to_dict()["score"] == 40
