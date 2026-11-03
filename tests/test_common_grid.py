"""Tests for the shared grid-game primitives in games/common/."""

import random

import pytest

from games.common.direction import Direction, DirectionQueue
from games.common.grid_move import candidate_head, clamp2d
from games.common.spawner import WeightedSpawner, should_despawn


def test_direction_from_name_3d_and_2d():
    assert Direction.from_name("up") == Direction(0, 1, 0)
    assert Direction.from_name_2d("up").as_2d() == (0, -1)
    assert Direction.from_name_2d("forward").as_2d() == (0, 1)
    with pytest.raises(ValueError):
        Direction.from_name("sideways")
    with pytest.raises(ValueError):
        Direction.from_name_2d("sideways")


def test_direction_is_opposite():
    assert Direction.from_name("left").is_opposite(Direction.from_name("right"))
    assert not Direction.from_name("left").is_opposite(Direction.from_name("up"))


def test_direction_queue_rejects_noop_and_reverse():
    q = DirectionQueue()
    last = Direction(1, 0, 0)
    assert q.push(Direction(1, 0, 0), last) is False       # same as current
    assert q.push(Direction(-1, 0, 0), last) is False      # 180-degree turn
    assert q.push(Direction(0, 1, 0), last) is True
    assert len(q) == 1
    assert q.pop() == Direction(0, 1, 0)
    assert q.pop() is None


def test_direction_queue_depth_limit_and_chain():
    q = DirectionQueue(max_depth=2)
    assert q.push(Direction(0, 1, 0), Direction(1, 0, 0))
    assert q.push(Direction(-1, 0, 0), q.peek_last())     # chained against last queued
    assert q.push(Direction(0, -1, 0), q.peek_last()) is False  # full
    assert q.peek_last() == Direction(-1, 0, 0)
    q.clear()
    assert len(q) == 0


def test_candidate_head_torus_wraps():
    assert candidate_head((9, 5, 6), Direction(1, 0, 0), 10, True) == (0, 5, 6)
    assert candidate_head((0, 0, 0), Direction(0, -1, 0), 10, True) == (0, 9, 0)


def test_candidate_head_wall_death_without_torus():
    assert candidate_head((9, 5, 6), Direction(1, 0, 0), 10, False) is None
    assert candidate_head((3, 5, 6), Direction(1, 0, 0), 10, False) == (4, 5, 6)


def test_clamp2d():
    assert clamp2d(-1, 99, 9) == (0, 8)
    assert clamp2d(4, 4, 9) == (4, 4)


def test_spawner_picks_free_cell_and_weighted_kind():
    sp = WeightedSpawner(random.Random(7), [("apple", 50), ("star", 14)])
    free = [(x, y, z) for x in range(3) for y in range(3) for z in range(3)]
    for _ in range(20):
        cell, kind = sp.spawn(free)
        assert cell in free and kind in ("apple", "star")
    assert sp.spawn([]) is None


def test_should_despawn():
    durations = {"apple": None, "star": 30.0}
    assert should_despawn(0, "apple", durations, 260) is False      # never
    assert should_despawn(29_900, "star", durations, 260) is True   # 30s reached
    assert should_despawn(1_000, "star", durations, 260) is False
    assert should_despawn(0, "unknown-kind", durations, 260) is False
