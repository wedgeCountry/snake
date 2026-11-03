"""Dungeon (RPG) game tests, incl. the combat system (weapons, traits,
levels, skills). The shared contract suite in tests/contracts/ also runs
against it via the registry."""

import random

import pytest

from games.dungeon.combat import make_hero, make_monster, resolve_encounter, strike
from games.dungeon.config import DungeonConfig
from games.dungeon.core import DungeonGame

FISTS = {"name": "Fists", "dmg": 0, "crit": 0.0}
CLAWS = {"name": "Claws", "dmg": 1, "crit": 0.0}


def _cfg(**kw):
    # deterministic combat: always hit, no crits, no weapon drops unless asked
    base = dict(hit_chance=1.0, weapon_drop_chance=0.0, hero_weapon="fists")
    base.update(kw)
    return DungeonConfig(**base)


def _game(seed=1, **kw):
    g = DungeonGame(rng=random.Random(seed))
    g.init(_cfg(**kw))
    return g


def _monster(x, y, hp, kind="monster", level=1, dmg=3, weapon=None, traits=None, skills=None):
    return {"name": "Boss" if kind == "boss" else "Monster", "x": x, "y": y, "kind": kind,
            "hp": hp, "max_hp": hp, "dmg": dmg, "level": level,
            "weapon": weapon or dict(CLAWS), "traits": traits or [], "skills": skills or []}


def test_init_places_hero_and_boss():
    g = _game()
    s = g.state()
    assert (s.hero["x"], s.hero["y"]) == (0, 0)
    assert s.hero["hp"] == s.hero["max_hp"] == 26  # 20 base + 6 from the Tough trait
    assert s.hero["weapon"]["name"] == "Fists"       # test config; default is Rusty Sword
    assert [t["name"] for t in s.hero["traits"]] == ["Tough"]
    assert s.hero["level"] == 1
    assert len(s.monsters) == 1 and s.monsters[0]["kind"] == "boss"
    assert (s.monsters[0]["x"], s.monsters[0]["y"]) == (7, 7)
    boss = s.monsters[0]
    assert boss["level"] == 5 and boss["weapon"]["name"] == "Doom Axe"
    assert boss["skills"], "boss has skills"


def test_hero_moves_with_direction():
    g = _game()
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert (g.state().hero["x"], g.state().hero["y"]) == (1, 0)


def test_combat_kills_monster_and_grants_loot():
    g = _game()
    s = g.state()
    s.monsters.append(_monster(1, 0, hp=4))  # dies to one hero hit (dmg 4 + fists 0)
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert all((m["x"], m["y"]) != (1, 0) for m in g.state().monsters)
    assert g.state().hero["xp"] == 10 and g.state().hero["gold"] == 5
    assert g.state().score == 10 + 2 * 5
    assert any("slain" in line for line in g.state().combat_log), "combat log records the fight"


def test_monster_hits_back_during_the_duel():
    g = _game()
    s = g.state()
    # hp 8: survives the hero's first 4-dmg strike, hits back for 3+1=4,
    # then dies in round 2 — the duel still ends with the hero winning
    s.monsters.append(_monster(1, 0, hp=8, dmg=3))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert all((m["x"], m["y"]) != (1, 0) for m in g.state().monsters)
    assert g.state().hero["hp"] == 26 - 4
    assert any("hits Hero" in line for line in g.state().combat_log)


def test_weapon_bonus_counts_toward_damage():
    g = _game()
    s = g.state()
    s.hero["weapon"] = {"name": "Iron Sword", "dmg": 4, "crit": 0.0}
    s.monsters.append(_monster(1, 0, hp=8, dmg=0, weapon=FISTS))  # 4+4 = 8 -> one-shot
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert all((m["x"], m["y"]) != (1, 0) for m in g.state().monsters)
    assert g.state().hero["hp"] == g.state().hero["max_hp"], "monster never got to hit back"


def test_armored_trait_reduces_damage_taken():
    g = _game()
    s = g.state()
    s.hero["traits"] = [{"name": "Armored", "key": "armored", "max_hp": 0, "dr": 2,
                         "dodge": 0.0, "lifesteal": 0, "berserk": 0}]
    s.monsters.append(_monster(1, 0, hp=8, dmg=3))  # raw 4, minus dr 2 -> 2 per round
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert g.state().hero["hp"] == 26 - 2


def test_skill_procs_and_multiplies_damage():
    cfg = _cfg()
    rng = random.Random(0)
    attacker = {"name": "Monster", "hp": 10, "max_hp": 10, "dmg": 5, "level": 1,
                "weapon": dict(FISTS), "traits": [],
                "skills": [{"name": "Power Strike", "chance": 1.0, "mult": 2.0}]}
    defender = {"name": "Hero", "hp": 50, "max_hp": 50, "traits": []}
    dmg, line = strike(rng, attacker, defender, cfg)
    assert dmg == 10 and defender["hp"] == 40
    assert "Power Strike" in line


def test_dodge_trait_can_cause_a_miss():
    cfg = _cfg(hit_chance=0.5)
    rng = random.Random(0)
    attacker = {"name": "Hero", "hp": 10, "max_hp": 10, "dmg": 5, "level": 1,
                "weapon": dict(FISTS), "traits": [], "skills": []}
    defender = {"name": "Monster", "hp": 50, "max_hp": 50,
                "traits": [{"name": "Nimble", "dodge": 1.0}]}
    dmg, line = strike(rng, attacker, defender, cfg)
    assert dmg == 0 and "misses" in line and defender["hp"] == 50


def test_resolve_encounter_decides_the_winner():
    cfg = _cfg()
    hero = make_hero(cfg)
    hero["dmg"] = 50
    monster = _monster(0, 0, hp=10)
    log = resolve_encounter(random.Random(0), hero, monster, cfg)
    assert monster["hp"] <= 0 and hero["hp"] > 0 and any("slain" in l for l in log)
    # and the other way round
    hero2 = make_hero(cfg)
    hero2["hp"] = 1
    monster2 = _monster(0, 0, hp=100, dmg=50)
    log2 = resolve_encounter(random.Random(0), hero2, monster2, cfg)
    assert hero2["hp"] <= 0 and monster2["hp"] > 0 and any("falls" in l for l in log2)


def test_weapon_drop_equips_better_weapon():
    g = _game(weapon_drop_chance=1.0)
    s = g.state()
    fangs = {"name": "Fangs", "dmg": 3, "crit": 0.0}
    s.monsters.append(_monster(1, 0, hp=4, weapon=fangs))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert g.state().hero["weapon"]["name"] == "Fangs", "hero took the better dropped weapon"


def test_level_up_grants_a_new_trait():
    g = _game()
    s = g.state()
    s.hero["xp"] = 30  # one level-up worth
    g.apply_action(0, {"direction": "right"})
    g.tick()
    hero = g.state().hero
    assert hero["level"] == 2 and hero["dmg"] == 6 and hero["xp"] == 0
    assert len(hero["traits"]) == 2 and hero["hp"] == hero["max_hp"]


def test_spawned_monsters_carry_weapons_traits_skills_and_levels():
    g = _game(seed=3)
    s = g.state()
    for _ in range(60):
        g.tick()
        if len(g.state().monsters) > 1:
            break
    spawned = [m for m in g.state().monsters if m["kind"] == "monster"]
    assert spawned, "a monster spawned within 60 turns"
    m = spawned[0]
    assert m["weapon"]["name"] and m["skills"] and m["level"] >= 1


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
    s.monsters.append(_monster(1, 0, hp=100, dmg=50))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert g.state().status == "dead"
    before = repr(g.state())
    g.tick()
    assert repr(g.state()) == before


def test_boss_kill_wins():
    g = _game()
    s = g.state()
    s.monsters[0]["hp"] = 4  # boss dies to one hero hit (dmg 4 + fists 0)
    # teleport hero next to the boss
    s.hero["x"], s.hero["y"] = 6, 7
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert g.state().status == "won"


def test_single_player_rejects_player_1():
    g = _game()
    with pytest.raises(ValueError):
        g.apply_action(1, {"direction": "left"})
