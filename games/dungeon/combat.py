"""Dungeon combat system + actor factories.

An encounter is round-based: each round the hero strikes, then the monster
strikes back, until one side dies (or `max_combat_rounds` runs out, in which
case the side with the higher remaining hp fraction wins). Damage comes from
base dmg + weapon + level scaling, modified by traits (armor/dodge/lifesteal/
berserk) and the attacker's skills (procced by chance). Everything is pure
functions over plain-dict actors with an injectable RNG, and every encounter
returns a short log for the UI.
"""

from __future__ import annotations

import random

from .config import SKILL_TABLE, TRAIT_TABLE, WEAPON_TABLE, DungeonConfig


def make_hero(cfg: DungeonConfig) -> dict:
    traits = [dict(TRAIT_TABLE[k], key=k) for k in cfg.hero_traits]
    max_hp = cfg.hero_hp + sum(t.get("max_hp", 0) for t in traits)
    return {
        "name": "Hero", "x": 0, "y": 0,
        "hp": max_hp, "max_hp": max_hp, "dmg": cfg.hero_dmg,
        "level": 1, "xp": 0, "gold": 0,
        "weapon": dict(WEAPON_TABLE[cfg.hero_weapon]),
        "traits": traits,
        "skills": [],
    }


def make_monster(rng: random.Random, x: int, y: int, cfg: DungeonConfig,
                 kind: str = "monster", level: int | None = None) -> dict:
    if kind == "boss":
        level = cfg.boss_level if level is None else level
        base_hp, base_dmg = cfg.boss_hp, cfg.boss_dmg
        weapon = dict(WEAPON_TABLE[cfg.boss_weapon])
        skill_pool = cfg.boss_skills
        name = "Boss"
    else:
        level = 1 if level is None else level
        base_hp, base_dmg = cfg.monster_hp, cfg.monster_dmg
        weapon = dict(WEAPON_TABLE[rng.choice(list(cfg.monster_weapons))])
        skill_pool = cfg.monster_skills
        name = "Monster"
    trait_key = rng.choice(list(TRAIT_TABLE))
    traits = [dict(TRAIT_TABLE[trait_key], key=trait_key)] if rng.random() < 0.5 else []
    skill_key = rng.choice(list(skill_pool))
    skills = [dict(SKILL_TABLE[skill_key], key=skill_key)]
    max_hp = base_hp + (level - 1) * 4 + sum(t.get("max_hp", 0) for t in traits)
    return {
        "name": name, "x": x, "y": y, "kind": kind,
        "hp": max_hp, "max_hp": max_hp,
        "dmg": base_dmg + (level - 1) * cfg.level_dmg_bonus,
        "level": level,
        "weapon": weapon,
        "traits": traits,
        "skills": skills,
    }


def random_trait(rng: random.Random, owned: list[str], cfg: DungeonConfig) -> dict | None:
    """A new trait the actor does not own yet (for hero level-ups)."""
    fresh = [k for k in TRAIT_TABLE if k not in owned]
    if not fresh or len(owned) >= cfg.max_traits:
        return None
    key = rng.choice(fresh)
    return dict(TRAIT_TABLE[key], key=key)


def _effect(actor: dict, key: str) -> float:
    return sum(t.get(key, 0) for t in actor.get("traits") or [])


def strike(rng: random.Random, attacker: dict, defender: dict,
           cfg: DungeonConfig) -> tuple[int, str]:
    """One attack from attacker onto defender; returns (damage, log line)."""
    a_name, d_name = attacker.get("name", "?"), defender.get("name", "?")
    dodge = _effect(defender, "dodge")
    if rng.random() >= max(0.0, cfg.hit_chance - dodge):
        return 0, f"{a_name} misses {d_name}"
    weapon = attacker.get("weapon") or {"dmg": 0, "crit": 0.0}
    dmg = (attacker.get("dmg", 0) + weapon.get("dmg", 0)
           + (attacker.get("level", 1) - 1) * cfg.level_dmg_bonus)
    notes: list[str] = []
    max_hp = attacker.get("max_hp") or 1
    berserk = _effect(attacker, "berserk")
    if berserk and attacker.get("hp", 0) * 2 < max_hp:
        dmg += berserk
        notes.append("berserk")
    for skill in attacker.get("skills") or []:
        if rng.random() < skill.get("chance", 0):
            if skill.get("mult"):
                dmg = int(dmg * skill["mult"])
            if skill.get("dmg"):
                dmg += skill["dmg"]
            if skill.get("heal"):
                heal = min(skill["heal"], max_hp - attacker.get("hp", 0))
                attacker["hp"] = attacker.get("hp", 0) + heal
                notes.append(f"{skill['name']} +{heal}HP")
            else:
                notes.append(skill["name"])
    crit = rng.random() < weapon.get("crit", 0.0)
    if crit:
        dmg = int(dmg * cfg.crit_multiplier)
    dmg = max(1, dmg - _effect(defender, "dr"))
    defender["hp"] = defender.get("hp", 0) - dmg
    lifesteal = _effect(attacker, "lifesteal")
    if lifesteal:
        attacker["hp"] = min(max_hp, attacker.get("hp", 0) + lifesteal)
    text = f"{a_name} hits {d_name} for {dmg}"
    if crit:
        text += " (crit!)"
    if notes:
        text += " [" + ", ".join(notes) + "]"
    return dmg, text


def resolve_encounter(rng: random.Random, hero: dict, monster: dict,
                      cfg: DungeonConfig) -> list[str]:
    """Fight the encounter to its conclusion, mutating both actors' hp.
    Returns the combat log; afterwards exactly one side has hp <= 0."""
    log = [f"{hero.get('name', 'Hero')} Lv{hero.get('level', 1)} engages "
           f"{monster.get('name', 'Monster')} Lv{monster.get('level', 1)}!"]
    for rnd in range(1, cfg.max_combat_rounds + 1):
        _, line = strike(rng, hero, monster, cfg)
        log.append(f"R{rnd} {line}")
        if monster.get("hp", 0) <= 0:
            log.append(f"{monster.get('name', 'Monster')} is slain!")
            monster["hp"] = 0
            return log
        _, line = strike(rng, monster, hero, cfg)
        log.append(f"R{rnd} {line}")
        if hero.get("hp", 0) <= 0:
            log.append(f"{hero.get('name', 'Hero')} falls!")
            hero["hp"] = 0
            return log
    hero_frac = hero.get("hp", 0) / max(1, hero.get("max_hp") or 1)
    mon_frac = monster.get("hp", 0) / max(1, monster.get("max_hp") or 1)
    if mon_frac >= hero_frac:
        hero["hp"] = 0
        log.append(f"{monster.get('name', 'Monster')} wins on stamina!")
    else:
        monster["hp"] = 0
        log.append(f"{hero.get('name', 'Hero')} wins on stamina!")
    return log
