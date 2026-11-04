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

from .config import ENCHANT_TABLE, LEGENDARY_TABLE, SKILL_TABLE, TRAIT_TABLE, WEAPON_TABLE, DungeonConfig


def make_hero(cfg: DungeonConfig) -> dict:
    traits = [dict(TRAIT_TABLE[k], key=k) for k in cfg.hero_traits]
    max_hp = cfg.hero_hp + sum(t.get("max_hp", 0) for t in traits)
    return {
        "name": "Hero", "x": 0, "y": 0,
        "hp": max_hp, "max_hp": max_hp, "dmg": cfg.hero_dmg,
        "level": 1, "xp": 0, "gold": 0,
        "weapon": _plain_weapon(WEAPON_TABLE[cfg.hero_weapon]),
        "traits": traits,
        "skills": [],
    }


def _plain_weapon(entry: dict) -> dict:
    w = dict(entry)
    w["enchant"] = None
    return w


def make_legendary(rng: random.Random) -> dict:
    """A random legendary weapon with its fixed starting enchantment."""
    key = rng.choice(list(LEGENDARY_TABLE))
    entry = LEGENDARY_TABLE[key]
    w = dict(entry, key=key)
    ench = entry.get("enchant")
    w["enchant"] = dict(ench, name=ENCHANT_TABLE[ench["school"]]["name"] + " +" + str(ench["level"])) if ench else None
    return w


def enchant_weapon(hero: dict, cfg: DungeonConfig, school: str | None = None) -> tuple[bool, str]:
    """Spend gold to raise the hero weapon's enchantment one level. The first
    enchant picks the school (default: fire); later ones keep it."""
    weapon = hero.get("weapon")
    if not weapon:
        return False, "no weapon to enchant"
    if school is not None and school not in ENCHANT_TABLE:
        return False, f"unknown enchant school: {school}"
    ench = weapon.get("enchant")
    if ench is None:
        school = school or "fire"
        level = 0
    else:
        school = ench["school"]  # an enchanted weapon keeps its school
        level = ench["level"]
    if level >= cfg.max_enchant_level:
        return False, weapon["name"] + " is already at max enchant"
    cost = cfg.enchant_cost_base * (level + 1)
    if hero.get("gold", 0) < cost:
        return False, f"not enough gold ({cost} needed)"
    hero["gold"] -= cost
    weapon["enchant"] = {"school": school, "level": level + 1,
                         "name": ENCHANT_TABLE[school]["name"] + " +" + str(level + 1)}
    return True, f"{hero.get('name', 'Hero')} enchants {weapon['name']} -> {weapon['enchant']['name']} (-{cost} gold)"


def make_hero_at_level(cfg: DungeonConfig, level: int) -> dict:
    """A hero of the given level with the same deterministic scaling the core
    applies on level-up (dmg +2, max_hp +6, full heal, one new trait per
    level up to max_traits, traits picked in table order). Used by the solver
    to prove playability at a specific character level."""
    hero = make_hero(cfg)
    owned = [t.get("key", t["name"]) for t in hero["traits"]]
    for _ in range(max(0, level - 1)):
        hero["level"] += 1
        hero["dmg"] += 2
        hero["max_hp"] += 6
        if len(hero["traits"]) < cfg.max_traits:
            for key in sorted(TRAIT_TABLE):
                if key not in owned:
                    trait = dict(TRAIT_TABLE[key], key=key)
                    hero["traits"].append(trait)
                    owned.append(key)
                    hero["max_hp"] += trait.get("max_hp", 0)
                    break
    hero["hp"] = hero["max_hp"]
    return hero


def make_monster(rng: random.Random, x: int, y: int, cfg: DungeonConfig,
                 kind: str = "monster", level: int | None = None) -> dict:
    if kind == "boss":
        level = cfg.boss_level if level is None else level
        base_hp, base_dmg = cfg.boss_hp, cfg.boss_dmg
        weapon = _plain_weapon(WEAPON_TABLE[cfg.boss_weapon])
        skill_pool = cfg.boss_skills
        name = "Boss"
    else:
        level = 1 if level is None else level
        base_hp, base_dmg = cfg.monster_hp, cfg.monster_dmg
        weapon = _plain_weapon(WEAPON_TABLE[rng.choice(list(cfg.monster_weapons))])
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
    # weapon enchantment effects (legendary objects / enchanting system)
    ench = weapon.get("enchant") or {}
    elvl = ench.get("level", 0)
    school = ench.get("school")
    if school == "fire" and elvl:
        dmg += ENCHANT_TABLE["fire"]["dmg_per_level"] * elvl
        notes.append(ench.get("name", "Immolation"))
    if school == "storm" and elvl and rng.random() < ENCHANT_TABLE["storm"]["double_chance_per_level"] * elvl:
        dmg = int(dmg * 2)
        notes.append(ench.get("name", "Stormforged") + " x2")
    dmg = max(1, dmg - _effect(defender, "dr"))
    defender["hp"] = defender.get("hp", 0) - dmg
    lifesteal = _effect(attacker, "lifesteal")
    if lifesteal:
        attacker["hp"] = min(max_hp, attacker.get("hp", 0) + lifesteal)
    if school == "blood" and elvl:
        heal = ENCHANT_TABLE["blood"]["heal_per_level"] + elvl - 1
        attacker["hp"] = min(max_hp, attacker.get("hp", 0) + heal)
        notes.append(f"{ench.get('name', 'Vampiric')} +{heal}HP")
    if school == "frost" and elvl and rng.random() < ENCHANT_TABLE["frost"]["freeze_chance_per_level"] * elvl:
        defender["frozen"] = True
        notes.append(ench.get("name", "Glacial") + " freezes")
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
        if monster.get("frozen"):
            monster["frozen"] = False
            log.append(f"R{rnd} {monster.get('name', 'Monster')} is frozen and cannot strike!")
        else:
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
