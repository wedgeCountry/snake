"""Tests for legendary objects and the enchanting system, incl. their
effects inside the combat resolver."""

import random

import pytest

from games.dungeon.combat import enchant_weapon, make_legendary, make_party, resolve_encounter, strike
from games.dungeon.config import DungeonConfig, ENCHANT_TABLE, LEGENDARY_TABLE
from games.dungeon.core import DungeonGame
from games.dungeon.levelgen import _dps, hit_probability
from games.registry import get

from test_dungeon import ScriptedRng, _cfg, _game, _monster, _open_field

FISTS = {"name": "Fists", "die": 4, "bonus": 0, "enchant": None}
CLAWS = {"name": "Claws", "die": 6, "bonus": 1, "enchant": None}


def test_enchant_costs_gold_and_levels_up_to_max():
    cfg = _cfg()
    member = make_party(cfg)[0]
    member["gold"] = 100
    ok, msg = enchant_weapon(member, cfg, "fire")
    assert ok and member["weapon"]["enchant"] == {"school": "fire", "level": 1, "name": "Immolation +1"}
    assert member["gold"] == 90
    enchant_weapon(member, cfg)  # keeps the school
    assert member["weapon"]["enchant"]["level"] == 2 and member["gold"] == 70
    enchant_weapon(member, cfg)
    assert member["weapon"]["enchant"]["level"] == 3 and member["gold"] == 40
    ok, _ = enchant_weapon(member, cfg)
    assert not ok and member["weapon"]["enchant"]["level"] == 3, "max enchant level enforced"


def test_enchant_rejects_unknown_school_and_poor_purse():
    cfg = _cfg()
    purse = make_party(cfg)[0]
    purse["gold"] = 100
    member = make_party(cfg)[1]
    ok, _ = enchant_weapon(member, cfg, "shadow", purse=purse)
    assert not ok and member["weapon"]["enchant"] is None
    purse["gold"] = 5
    ok, _ = enchant_weapon(member, cfg, "fire", purse=purse)
    assert not ok, "not enough gold in the party purse"


def test_fire_enchant_adds_damage_in_combat():
    cfg = _cfg()
    attacker = {"name": "Warrior", "hp": 10, "max_hp": 10, "ac": 10, "attack": 5, "level": 1,
                "weapon": dict(FISTS, enchant={"school": "fire", "level": 2, "name": "Immolation +2"}),
                "traits": [], "skills": []}
    defender = {"name": "M", "hp": 50, "max_hp": 50, "ac": 10, "traits": []}
    dmg, line = strike(ScriptedRng(rands=[15, 4], randoms=[0.99]), attacker, defender, cfg)
    assert dmg == 4 + 2 * 2 and "Immolation" in line


def test_blood_enchant_heals_the_attacker():
    cfg = _cfg()
    attacker = {"name": "Warrior", "hp": 5, "max_hp": 20, "ac": 10, "attack": 5, "level": 1,
                "weapon": dict(FISTS, enchant={"school": "blood", "level": 3, "name": "Vampiric +3"}),
                "traits": [], "skills": []}
    defender = {"name": "M", "hp": 50, "max_hp": 50, "ac": 10, "traits": []}
    strike(ScriptedRng(rands=[15, 4], randoms=[0.99]), attacker, defender, cfg)
    assert attacker["hp"] == 5 + 3, "blood heals 1+level-1 = 3 per hit"


def test_storm_enchant_can_double_the_hit():
    cfg = _cfg()
    attacker = {"name": "Warrior", "hp": 10, "max_hp": 10, "ac": 10, "attack": 5, "level": 1,
                "weapon": dict(FISTS, enchant={"school": "storm", "level": 10, "name": "Stormforged +10"}),
                "traits": [], "skills": []}
    defender = {"name": "M", "hp": 50, "max_hp": 50, "ac": 10, "traits": []}
    dmg, line = strike(ScriptedRng(rands=[15, 4], randoms=[0.99, 0.0]), attacker, defender, cfg)
    assert dmg == 8 and "x2" in line  # 0.15*10 >= 1 -> always doubles


def test_frost_enchant_freezes_and_skips_the_monster_strike():
    cfg = _cfg()
    party = make_party(cfg)
    party[0]["weapon"] = dict(FISTS, enchant={"school": "frost", "level": 10, "name": "Glacial +10"})
    party[0]["attack"] = 50
    monster = _monster(0, 0, hp=100, attack=50)  # survives round 1, then stays frozen
    log = resolve_encounter(ScriptedRng(rands=[20, 1, 1, 20], randoms=[0.99] * 80),
                            party, monster, cfg)
    assert monster["hp"] <= 0
    assert all(m["hp"] == m["max_hp"] for m in party), "frozen monster never struck back"
    assert any("frozen" in line for line in log)


def test_legendaries_have_fixed_enchant_and_strong_stats():
    for key, entry in LEGENDARY_TABLE.items():
        w = make_legendary(random.Random(0))
        assert w["enchant"] is not None and w["enchant"]["school"] in ENCHANT_TABLE
        break  # structure checked; randomness picks one
    best = max(LEGENDARY_TABLE.values(), key=lambda w: w["die"])
    assert best["die"] >= 10 and best["enchant"]["level"] == 1


def test_boss_always_drops_a_legendary():
    g = _game()
    s = g.state()
    s.party[0]["gold"] = 0
    s.monsters.append(_monster(1, 0, hp=4, kind="boss", attack=0))
    # warrior first in initiative, natural-20 crit one-shots the boss
    g._rng = ScriptedRng(rands=[20, 1, 1, 1, 20, 8, 8], randoms=[0.99, 0.0, 0.99])
    for m in s.party:
        m["x"], m["y"] = 0, 0
    g.apply_action(0, {"direction": "right"})
    g.tick()
    dropped = [m["weapon"] for m in g.state().party if m["weapon"].get("key") in LEGENDARY_TABLE]
    assert dropped, "the boss dropped a legendary for some member"
    assert dropped[0]["enchant"] is not None
    assert g.state().status == "won"
    assert any("legendary" in line for line in g.state().combat_log)


def test_enchant_action_via_apply_action():
    g = _game()
    s = _open_field(g, ScriptedRng())
    s.party[0]["gold"] = 50
    g.apply_action(0, {"enchant": "frost"})
    assert s.party[0]["weapon"]["enchant"]["school"] == "frost"
    assert s.party[0]["gold"] == 40
    assert any("enchant" in line.lower() for line in s.combat_log)
    with pytest.raises(ValueError):
        g.apply_action(0, {"enchant": "shadow"})
    with pytest.raises(ValueError):
        g.apply_action(0, {"teleport": "nowhere"})


def test_enchant_raises_expected_dps_in_measurement():
    cfg = _cfg()
    member = make_party(cfg)[0]
    member["weapon"] = dict(FISTS)
    ac = 12
    base = _dps(member, cfg, ac)
    member["weapon"] = dict(FISTS, enchant={"school": "fire", "level": 3, "name": "Immolation +3"})
    assert _dps(member, cfg, ac) == pytest.approx(
        base + hit_probability(member["attack"], ac) * (1 + 1 / 20) * 2 * 3)


def test_serializer_exposes_party_weapon_enchant():
    g = _game()
    s = _open_field(g, ScriptedRng())
    s.party[0]["gold"] = 50
    g.apply_action(0, {"enchant": "fire"})
    d = get("dungeon").serialize(g.state())
    assert d["party"][0]["weapon"]["enchant"]["school"] == "fire"
