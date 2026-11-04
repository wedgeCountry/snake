"""Tests for legendary objects and the enchanting system, incl. their
effects inside the combat resolver."""

import random

import pytest

from games.dungeon.combat import enchant_weapon, make_hero, make_legendary, resolve_encounter, strike
from games.dungeon.config import DungeonConfig, ENCHANT_TABLE, LEGENDARY_TABLE
from games.dungeon.core import DungeonGame
from games.dungeon.levelgen import _dps
from games.registry import get

FISTS = {"name": "Fists", "dmg": 0, "crit": 0.0, "enchant": None}
CLAWS = {"name": "Claws", "dmg": 1, "crit": 0.0, "enchant": None}


def _cfg(**kw):
    base = dict(hit_chance=1.0, weapon_drop_chance=0.0, hero_weapon="fists")
    base.update(kw)
    return DungeonConfig(**base)


def _game(seed=1, **kw):
    g = DungeonGame(rng=random.Random(seed))
    g.init(_cfg(**kw))
    s = g.state()
    s.monsters.clear()
    s.potions.clear()
    s.hero["x"], s.hero["y"] = 0, 0
    return g


def _monster(x, y, hp, kind="monster", dmg=3):
    return {"name": "Boss" if kind == "boss" else "Monster", "x": x, "y": y, "kind": kind,
            "hp": hp, "max_hp": hp, "dmg": dmg, "level": 1,
            "weapon": dict(CLAWS), "traits": [], "skills": []}


def test_enchant_costs_gold_and_levels_up_to_max():
    cfg = _cfg()
    hero = make_hero(cfg)
    hero["gold"] = 100
    ok, msg = enchant_weapon(hero, cfg, "fire")
    assert ok and hero["weapon"]["enchant"] == {"school": "fire", "level": 1, "name": "Immolation +1"}
    assert hero["gold"] == 90
    enchant_weapon(hero, cfg)  # keeps the school
    assert hero["weapon"]["enchant"]["level"] == 2 and hero["gold"] == 70
    enchant_weapon(hero, cfg)
    assert hero["weapon"]["enchant"]["level"] == 3 and hero["gold"] == 40
    ok, _ = enchant_weapon(hero, cfg)
    assert not ok and hero["weapon"]["enchant"]["level"] == 3, "max enchant level enforced"


def test_enchant_rejects_unknown_school_and_poor_hero():
    cfg = _cfg()
    hero = make_hero(cfg)
    hero["gold"] = 100
    ok, _ = enchant_weapon(hero, cfg, "shadow")
    assert not ok and hero["weapon"]["enchant"] is None
    hero["gold"] = 5
    ok, _ = enchant_weapon(hero, cfg, "fire")
    assert not ok, "not enough gold"


def test_fire_enchant_adds_damage_in_combat():
    cfg = _cfg()
    rng = random.Random(0)
    attacker = {"name": "Hero", "hp": 10, "max_hp": 10, "dmg": 5, "level": 1,
                "weapon": dict(FISTS, enchant={"school": "fire", "level": 2, "name": "Immolation +2"}),
                "traits": [], "skills": []}
    defender = {"name": "M", "hp": 50, "max_hp": 50, "traits": []}
    dmg, line = strike(rng, attacker, defender, cfg)
    assert dmg == 5 + 2 * 2 and "Immolation" in line


def test_blood_enchant_heals_the_attacker():
    cfg = _cfg()
    rng = random.Random(0)
    attacker = {"name": "Hero", "hp": 5, "max_hp": 20, "dmg": 5, "level": 1,
                "weapon": dict(FISTS, enchant={"school": "blood", "level": 3, "name": "Vampiric +3"}),
                "traits": [], "skills": []}
    defender = {"name": "M", "hp": 50, "max_hp": 50, "traits": []}
    strike(rng, attacker, defender, cfg)
    assert attacker["hp"] == 5 + 3, "blood heals 1+level-1 = 3 per hit"


def test_storm_enchant_can_double_the_hit():
    cfg = _cfg()
    rng = random.Random(0)
    attacker = {"name": "Hero", "hp": 10, "max_hp": 10, "dmg": 5, "level": 1,
                "weapon": dict(FISTS, enchant={"school": "storm", "level": 10, "name": "Stormforged +10"}),
                "traits": [], "skills": []}
    defender = {"name": "M", "hp": 50, "max_hp": 50, "traits": []}
    dmg, line = strike(rng, attacker, defender, cfg)
    assert dmg == 10 and "x2" in line  # 0.15*10 >= 1 -> always doubles


def test_frost_enchant_freezes_and_skips_the_monster_strike():
    cfg = _cfg()
    hero = make_hero(cfg)
    hero["weapon"] = dict(FISTS, enchant={"school": "frost", "level": 10, "name": "Glacial +10"})
    monster = _monster(0, 0, hp=8, dmg=50)
    log = resolve_encounter(random.Random(0), hero, monster, cfg)
    assert monster["hp"] <= 0
    assert hero["hp"] == hero["max_hp"], "frozen monster never struck back"
    assert any("frozen" in line for line in log)


def test_legendaries_have_fixed_enchant_and_strong_stats():
    for key, entry in LEGENDARY_TABLE.items():
        w = make_legendary(random.Random(0))
        assert w["enchant"] is not None and w["enchant"]["school"] in ENCHANT_TABLE
        break  # structure checked; randomness picks one
    best = max(LEGENDARY_TABLE.values(), key=lambda w: w["dmg"])
    assert best["dmg"] >= 5 and best["enchant"]["level"] == 1


def test_boss_always_drops_a_legendary():
    g = _game()
    s = g.state()
    s.hero["gold"] = 0
    s.monsters.append(_monster(1, 0, hp=4, kind="boss", dmg=0))  # one-shot kill
    g.apply_action(0, {"direction": "right"})
    g.tick()
    w = g.state().hero["weapon"]
    assert w.get("key") in LEGENDARY_TABLE, f"boss dropped a legendary, got {w}"
    assert w["enchant"] is not None
    assert g.state().status == "won"
    assert any("legendary" in line for line in g.state().combat_log)


def test_enchant_action_via_apply_action():
    g = _game()
    s = g.state()
    s.hero["gold"] = 50
    g.apply_action(0, {"enchant": "frost"})
    assert s.hero["weapon"]["enchant"]["school"] == "frost"
    assert s.hero["gold"] == 40
    assert any("enchant" in line.lower() for line in s.combat_log)
    with pytest.raises(ValueError):
        g.apply_action(0, {"enchant": "shadow"})
    with pytest.raises(ValueError):
        g.apply_action(0, {"teleport": "nowhere"})


def test_enchant_raises_expected_dps_in_measurement_and_solver_model():
    cfg = _cfg()
    hero = make_hero(cfg)
    base = _dps(hero, cfg)
    hero["weapon"] = dict(FISTS, enchant={"school": "fire", "level": 3, "name": "Immolation +3"})
    assert _dps(hero, cfg) == base + 2 * 3


def test_serializer_exposes_weapon_enchant():
    g = _game()
    s = g.state()
    s.hero["gold"] = 50
    g.apply_action(0, {"enchant": "fire"})
    d = get("dungeon").serialize(g.state())
    assert d["hero"]["weapon"]["enchant"]["school"] == "fire"
