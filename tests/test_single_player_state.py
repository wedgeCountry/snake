"""Tests for GameSinglePlayerState, the single-player wrapper used in tests."""

import random

from games.snake.config import SnakeConfig
from games.snake.core import SnakeGame
from games.snake.models import GameSinglePlayerState


def make_state(mode: str = "single", seed: int = 1):
    game = SnakeGame(rng=random.Random(seed))
    return game.init(SnakeConfig(torus=True, grid_size=10, mode=mode))


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
