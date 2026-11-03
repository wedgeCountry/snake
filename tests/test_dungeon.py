"""Dungeon (RPG) game tests. The shared contract suite in tests/contracts/
also runs against it via the registry."""

import random

import pytest

from games.dungeon.config import DungeonConfig
from games.dungeon.core import DungeonGame


def _game(seed=1):
    g = DungeonGame(rng=random.Random(seed))
    g.init(DungeonConfig())
    return g


def test_init_places_hero_and_boss():
    g = _game()
    s = g.state()
    assert (s.hero["x"], s.hero["y"]) == (0, 0)
    assert s.hero["hp"] == s.hero["max_hp"] == 20
    assert len(s.monsters) == 1 and s.monsters[0]["kind"] == "boss"
    assert (s.monsters[0]["x"], s.monsters[0]["y"]) == (7, 7)


def test_hero_moves_with_direction():
    g = _game()
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert (g.state().hero["x"], g.state().hero["y"]) == (1, 0)


def test_combat_kills_monster_and_grants_loot():
    g = _game()
    s = g.state()
    s.monsters.append({"x": 1, "y": 0, "hp": 4, "kind": "monster"})  # dies to one hit (dmg 4)
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert all((m["x"], m["y"]) != (1, 0) for m in g.state().monsters)
    assert g.state().hero["xp"] == 10 and g.state().hero["gold"] == 5
    assert g.state().score == 10 + 2 * 5


def test_monster_hits_back_when_surviving():
    g = _game()
    s = g.state()
    s.monsters.append({"x": 1, "y": 0, "hp": 100, "kind": "monster"})
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert g.state().hero["hp"] == 20 - 3


def test_potion_heals_hero():
    g = _game()
    s = g.state()
    s.hero["hp"] = 5
    s.potions.append((1, 0))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert g.state().hero["hp"] == 5 + 8
    assert (1, 0) not in g.state().potions


def test_hero_death_is_terminal_and_stable():
    g = _game()
    s = g.state()
    s.hero["hp"] = 1
    s.monsters.append({"x": 1, "y": 0, "hp": 100, "kind": "monster"})
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert g.state().status == "dead"
    before = repr(g.state())
    g.tick()
    assert repr(g.state()) == before


def test_boss_kill_wins():
    g = _game()
    s = g.state()
    s.monsters[0]["hp"] = 4  # boss dies to one hero hit
    # teleport hero next to the boss
    s.hero["x"], s.hero["y"] = 6, 7
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert g.state().status == "won"


def test_single_player_rejects_player_1():
    g = _game()
    with pytest.raises(ValueError):
        g.apply_action(1, {"direction": "left"})
