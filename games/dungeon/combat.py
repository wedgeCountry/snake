"""Dungeon combat system + actor factories (simplified Baldur's Gate rules).

The party (one hero per class in `party_classes`) fights monster encounters.
Combat is D&D-style: each strike rolls a d20 — natural 1 always misses,
natural 20 always hits and doubles the damage dice, otherwise the strike hits
when d20 + attack bonus >= defender AC. Damage comes from the weapon's damage
die + bonus + level scaling, modified by traits (armor/dodge/lifesteal/berserk)
and the attacker's skills (procced by chance). Encounters are round-based with
initiative order (d20 + init, highest first); monsters focus the weakest
living party member. Everything is pure functions over plain-dict actors with
an injectable RNG, and every encounter returns a short log for the UI.
"""

from __future__ import annotations

import random

from .config import ENCHANT_TABLE, LEGENDARY_TABLE, PARTY_TABLE, SKILL_TABLE, TRAIT_TABLE, WEAPON_TABLE, DungeonConfig


def make_party(cfg: DungeonConfig) -> list[dict]:
    """The hero party: one member per class in `party_classes`. Index 0 is the
    leader and carries the party gold purse; all members share the grid cell."""
    party: list[dict] = []
    for i, key in enumerate(cfg.party_classes):
        cls = PARTY_TABLE[key]
        traits = [dict(TRAIT_TABLE[k], key=k) for k in cls.get("traits", ())]
        skills = [dict(SKILL_TABLE[k], key=k) for k in cls.get("skills", ())]
        max_hp = cls["hp"] + sum(t.get("max_hp", 0) for t in traits)
        member = {
            "name": cls["name"], "class": key, "x": 0, "y": 0,
            "hp": max_hp, "max_hp": max_hp,
            "ac": cls["ac"], "attack": cls["attack"], "init": cls["init"],
            "level": 1, "xp": 0,
            "weapon": _plain_weapon(WEAPON_TABLE[cls["weapon"]]),
            "traits": traits, "skills": skills,
        }
        if i == 0:
            member["gold"] = 0  # the leader holds the party purse
        party.append(member)
    return party


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


def enchant_weapon(actor: dict, cfg: DungeonConfig, school: str | None = None,
                   purse: dict | None = None) -> tuple[bool, str]:
    """Spend gold (from `purse`, default: the actor itself) to raise the
    actor's weapon enchantment one level. The first enchant picks the school
    (default: fire); later ones keep it."""
    purse = purse if purse is not None else actor
    weapon = actor.get("weapon")
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
    if purse.get("gold", 0) < cost:
        return False, f"not enough gold ({cost} needed)"
    purse["gold"] -= cost
    weapon["enchant"] = {"school": school, "level": level + 1,
                         "name": ENCHANT_TABLE[school]["name"] + " +" + str(level + 1)}
    return True, f"{actor.get('name', 'Hero')} enchants {weapon['name']} -> {weapon['enchant']['name']} (-{cost} gold)"


def make_party_at_level(cfg: DungeonConfig, level: int) -> list[dict]:
    """A party of the given level with the same deterministic scaling the core
    applies on level-up (attack +level_attack_bonus, max_hp +level_hp_bonus,
    full heal, one new trait per member per level up to max_traits, traits
    picked in table order). Used by the solver to prove playability at a
    specific party level."""
    party = make_party(cfg)
    for member in party:
        owned = [t.get("key", t["name"]) for t in member["traits"]]
        for _ in range(max(0, level - 1)):
            member["level"] += 1
            member["attack"] += cfg.level_attack_bonus
            member["max_hp"] += cfg.level_hp_bonus
            if len(member["traits"]) < cfg.max_traits:
                for key in sorted(TRAIT_TABLE):
                    if key not in owned:
                        trait = dict(TRAIT_TABLE[key], key=key)
                        member["traits"].append(trait)
                        owned.append(key)
                        member["max_hp"] += trait.get("max_hp", 0)
                        break
        member["hp"] = member["max_hp"]
    return party


def make_monster(rng: random.Random, x: int, y: int, cfg: DungeonConfig,
                 kind: str = "monster", level: int | None = None) -> dict:
    if kind == "boss":
        level = cfg.boss_level if level is None else level
        base_hp, base_ac, base_attack, base_init = cfg.boss_hp, cfg.boss_ac, cfg.boss_attack, cfg.boss_init
        weapon = _plain_weapon(WEAPON_TABLE[cfg.boss_weapon])
        skill_pool = cfg.boss_skills
        name = "Boss"
    else:
        level = 1 if level is None else level
        base_hp, base_ac, base_attack, base_init = cfg.monster_hp, cfg.monster_ac, cfg.monster_attack, cfg.monster_init
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
        "ac": base_ac + (level - 1) // 2,
        "attack": base_attack + (level - 1),
        "init": base_init,
        "level": level,
        "weapon": weapon,
        "traits": traits,
        "skills": skills,
    }


def random_trait(rng: random.Random, owned: list[str], cfg: DungeonConfig) -> dict | None:
    """A new trait the actor does not own yet (for member level-ups)."""
    fresh = [k for k in TRAIT_TABLE if k not in owned]
    if not fresh or len(owned) >= cfg.max_traits:
        return None
    key = rng.choice(fresh)
    return dict(TRAIT_TABLE[key], key=key)


def _effect(actor: dict, key: str) -> float:
    return sum(t.get(key, 0) for t in actor.get("traits") or [])


def roll_attack(rng: random.Random, attacker: dict, defender: dict,
                cfg: DungeonConfig) -> tuple[int, bool, bool]:
    """One d20 attack roll: returns (roll, hit, crit). Natural 1 always misses,
    natural 20 always crits (and hits); otherwise hit iff roll + attack >= AC,
    after the defender's dodge trait eats the strike by chance."""
    if rng.random() < _effect(defender, "dodge"):
        return 0, False, False
    roll = rng.randint(1, 20)
    if roll == 1:
        return roll, False, False
    if roll == 20:
        return roll, True, True
    return roll, roll + attacker.get("attack", 0) >= defender.get("ac", 10), False


def strike(rng: random.Random, attacker: dict, defender: dict,
           cfg: DungeonConfig) -> tuple[int, str]:
    """One attack from attacker onto defender; returns (damage, log line)."""
    a_name, d_name = attacker.get("name", "?"), defender.get("name", "?")
    roll, hit, crit = roll_attack(rng, attacker, defender, cfg)
    if not hit:
        return 0, f"{a_name} misses {d_name}" + (f" (rolled {roll})" if roll else "")
    weapon = attacker.get("weapon") or {"die": 4, "bonus": 0}
    dice = 2 if crit else 1
    dmg = sum(rng.randint(1, weapon.get("die", 4)) for _ in range(dice))
    dmg += weapon.get("bonus", 0) + (attacker.get("level", 1) - 1) * cfg.level_dmg_bonus
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
    text = f"{a_name} hits {d_name} for {dmg} (d20 {roll}{'+crit' if crit else ''})"
    if notes:
        text += " [" + ", ".join(notes) + "]"
    return dmg, text


def _living(party: list[dict]) -> list[dict]:
    return [m for m in party if m.get("hp", 0) > 0]


def resolve_encounter(rng: random.Random, party: list[dict], monster: dict,
                      cfg: DungeonConfig) -> list[str]:
    """Fight the encounter to its conclusion, mutating hp on both sides.
    Initiative (d20 + init, highest first) decides the order in which the
    living party members and the monster strike each round; the monster
    focuses the living member with the lowest hp. Returns the combat log;
    afterwards the monster is dead or the whole party is."""
    members = _living(party)
    log = [f"Party (Lv{members[0].get('level', 1) if members else 1}) engages "
           f"{monster.get('name', 'Monster')} Lv{monster.get('level', 1)}!"]
    order = sorted(
        [("member", m) for m in members] + [("monster", monster)],
        key=lambda c: -(rng.randint(1, 20) + c[1].get("init", 0)))
    for rnd in range(1, cfg.max_combat_rounds + 1):
        for kind, actor in order:
            if kind == "member":
                if actor.get("hp", 0) <= 0 or monster.get("hp", 0) <= 0:
                    continue
                _, line = strike(rng, actor, monster, cfg)
                log.append(f"R{rnd} {line}")
                if monster.get("hp", 0) <= 0:
                    monster["hp"] = 0
                    log.append(f"{monster.get('name', 'Monster')} is slain!")
                    return log
            else:
                if monster.get("hp", 0) <= 0 or not _living(party):
                    continue
                if monster.get("frozen"):
                    monster["frozen"] = False
                    log.append(f"R{rnd} {monster.get('name', 'Monster')} is frozen and cannot strike!")
                    continue
                target = min(_living(party), key=lambda m: m.get("hp", 0))
                _, line = strike(rng, monster, target, cfg)
                log.append(f"R{rnd} {line}")
                if not _living(party):
                    for m in party:
                        m["hp"] = min(m.get("hp", 0), 0)
                    log.append("The party falls!")
                    return log
    party_frac = sum(m.get("hp", 0) for m in party) / max(1, sum(m.get("max_hp", 1) for m in party))
    mon_frac = monster.get("hp", 0) / max(1, monster.get("max_hp") or 1)
    if mon_frac >= party_frac:
        for m in party:
            m["hp"] = min(m.get("hp", 0), 0)
        log.append(f"{monster.get('name', 'Monster')} wins on stamina!")
    else:
        monster["hp"] = 0
        log.append("The party wins on stamina!")
    return log
