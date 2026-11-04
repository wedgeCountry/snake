"""Tests for the randomized dungeon level generator and its difficulty
measurement (duel-threat model: how close monster stats are to the hero's)."""

import random

from games.dungeon.combat import make_hero
from games.dungeon.config import DungeonConfig
from games.dungeon.core import DungeonGame
from games.dungeon.levelgen import (
    MAX_DIFFICULTY,
    MIN_DIFFICULTY,
    clamp_difficulty,
    duel_threat,
    generate_level,
    generate_level_with_target,
    measure_difficulty,
)
from games.registry import get


def test_clamp_difficulty_stays_in_1_to_10():
    assert clamp_difficulty(0) == 1
    assert clamp_difficulty(99) == 10
    assert clamp_difficulty(7) == 7
    assert clamp_difficulty(-3) == 1
    assert clamp_difficulty("x") == 5


def test_generate_level_layout_is_valid():
    cfg = DungeonConfig()
    lvl = generate_level(random.Random(1), cfg, 6)
    n = lvl["grid_size"]
    corners = {(0, 0), (n - 1, 0), (0, n - 1), (n - 1, n - 1)}
    assert lvl["hero_start"] in corners
    hx, hy = lvl["hero_start"]
    # boss sits in the diagonally opposite corner
    assert (lvl["boss"]["x"], lvl["boss"]["y"]) == (n - 1 - hx, n - 1 - hy)
    cells = ([lvl["hero_start"], (lvl["boss"]["x"], lvl["boss"]["y"])]
             + [(m["x"], m["y"]) for m in lvl["monsters"]] + list(lvl["potions"]))
    assert len(set(cells)) == len(cells), "no overlapping placements"
    assert all(0 <= x < n and 0 <= y < n for x, y in cells)
    assert lvl["monsters"] and lvl["potions"]
    assert all(m["weapon"]["name"] and m["skills"] and m["level"] >= 1 for m in lvl["monsters"])


def test_harder_levels_have_more_stronger_monsters_and_fewer_potions():
    cfg = DungeonConfig()
    easy = generate_level(random.Random(5), cfg, 1)
    hard = generate_level(random.Random(5), cfg, 10)
    assert len(hard["monsters"]) > len(easy["monsters"])
    assert sum(m["level"] for m in hard["monsters"]) > sum(m["level"] for m in easy["monsters"])
    assert len(hard["potions"]) <= len(easy["potions"])


def test_duel_threat_measures_stat_closeness_and_caps_at_lethal():
    cfg = DungeonConfig()
    hero = make_hero(cfg)
    weak = {"name": "M", "hp": 1, "max_hp": 1, "dmg": 1, "level": 1,
            "weapon": {"name": "Claws", "dmg": 0, "crit": 0.0}, "traits": [], "skills": []}
    strong = {"name": "M", "hp": 1000, "max_hp": 1000, "dmg": 100, "level": 5,
              "weapon": {"name": "Doom Axe", "dmg": 8, "crit": 0.2}, "traits": [], "skills": []}
    assert 0 < duel_threat(weak, hero, cfg) < 0.5
    assert duel_threat(strong, hero, cfg) == 1.0, "overwhelming monster = lethal (capped)"


def test_measure_difficulty_rises_with_monster_stats():
    cfg = DungeonConfig()
    hero = make_hero(cfg)
    base = generate_level(random.Random(1), cfg, 1)
    easy = measure_difficulty(base, hero, cfg)
    beefed = generate_level(random.Random(1), cfg, 1)
    for m in beefed["monsters"]:
        m["dmg"] += 20
        m["level"] = 5
        m["max_hp"] += 100
        m["hp"] = m["max_hp"]
    hard = measure_difficulty(beefed, hero, cfg)
    assert easy < hard <= MAX_DIFFICULTY


def test_measured_difficulty_tracks_the_1_to_10_target():
    cfg = DungeonConfig()
    for d in range(MIN_DIFFICULTY, MAX_DIFFICULTY + 1):
        for seed in (1, 7, 42):
            lvl = generate_level_with_target(random.Random(seed), cfg, d)
            assert MIN_DIFFICULTY <= lvl["measured_difficulty"] <= MAX_DIFFICULTY
            assert abs(lvl["measured_difficulty"] - d) <= 1.6, (d, lvl["measured_difficulty"])
    easy = generate_level_with_target(random.Random(3), cfg, 1)["measured_difficulty"]
    hard = generate_level_with_target(random.Random(3), cfg, 10)["measured_difficulty"]
    assert hard > easy


def test_generator_is_deterministic_per_seed():
    cfg = DungeonConfig()
    a = generate_level_with_target(random.Random(9), cfg, 6)
    b = generate_level_with_target(random.Random(9), cfg, 6)
    assert a == b


def test_game_init_uses_generator_and_stores_difficulty():
    g = DungeonGame(rng=random.Random(1))
    g.init(DungeonConfig(difficulty=8))
    s = g.state()
    assert s.difficulty == 8
    assert MIN_DIFFICULTY <= s.level_difficulty <= MAX_DIFFICULTY
    n = s.grid_size
    assert (s.hero["x"], s.hero["y"]) in {(0, 0), (n - 1, 0), (0, n - 1), (n - 1, n - 1)}
    boss = next(m for m in s.monsters if m["kind"] == "boss")
    assert (boss["x"], boss["y"]) == (n - 1 - s.hero["x"], n - 1 - s.hero["y"])


def test_serializer_exposes_requested_and_measured_difficulty():
    g = DungeonGame(rng=random.Random(1))
    g.init(DungeonConfig(difficulty=3))
    d = get("dungeon").serialize(g.state())
    assert d["difficulty"] == 3
    assert MIN_DIFFICULTY <= d["levelDifficulty"] <= MAX_DIFFICULTY
