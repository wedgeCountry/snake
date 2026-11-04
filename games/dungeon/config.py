"""Dungeon (RPG) rule configuration, incl. the combat system's data tables.

Actors (hero + monsters) carry a weapon, traits and a level; monsters also
carry skills. All tables are plain data so state stays JSON-serializable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..engine import RuleConfig

GRID_SIZE = 8
MAX_TURNS = 200
HERO_HP = 20
HERO_DMG = 4
MONSTER_HP = 8
MONSTER_DMG = 3
BOSS_HP = 30
BOSS_DMG = 6
BOSS_LEVEL = 5
POTION_HEAL = 8
SPAWN_CHANCE = 0.35
XP_PER_KILL = 10
XP_LEVEL_UP = 30

# weapon key -> {name, dmg bonus, crit chance}
WEAPON_TABLE: dict[str, dict] = {
    "fists":         {"name": "Fists",          "dmg": 0, "crit": 0.00},
    "rusty_sword":   {"name": "Rusty Sword",    "dmg": 2, "crit": 0.05},
    "iron_sword":    {"name": "Iron Sword",     "dmg": 4, "crit": 0.10},
    "knights_blade": {"name": "Knight's Blade", "dmg": 6, "crit": 0.15},
    "claws":         {"name": "Claws",          "dmg": 1, "crit": 0.05},
    "fangs":         {"name": "Fangs",          "dmg": 3, "crit": 0.10},
    "venom_sting":   {"name": "Venom Sting",    "dmg": 4, "crit": 0.15},
    "doom_axe":      {"name": "Doom Axe",       "dmg": 8, "crit": 0.20},
}

# trait key -> passive effects
TRAIT_TABLE: dict[str, dict] = {
    "tough":    {"name": "Tough",    "max_hp": 6, "dr": 0, "dodge": 0.00, "lifesteal": 0, "berserk": 0},
    "armored":  {"name": "Armored",  "max_hp": 0, "dr": 2, "dodge": 0.00, "lifesteal": 0, "berserk": 0},
    "nimble":   {"name": "Nimble",   "max_hp": 0, "dr": 0, "dodge": 0.15, "lifesteal": 0, "berserk": 0},
    "vampiric": {"name": "Vampiric", "max_hp": 0, "dr": 0, "dodge": 0.00, "lifesteal": 2, "berserk": 0},
    "berserk":  {"name": "Berserk",  "max_hp": 0, "dr": 0, "dodge": 0.00, "lifesteal": 0, "berserk": 2},
}

# skill key -> active effect procced during combat (mult = damage multiplier,
# dmg = flat bonus damage, heal = self-heal)
SKILL_TABLE: dict[str, dict] = {
    "power_strike": {"name": "Power Strike", "chance": 0.25, "mult": 1.5},
    "poison":       {"name": "Poison",       "chance": 0.30, "dmg": 2},
    "regenerate":   {"name": "Regenerate",   "chance": 0.20, "heal": 4},
    "doom_slam":    {"name": "Doom Slam",    "chance": 0.30, "mult": 2.0},
}


@dataclass(frozen=True)
class DungeonConfig(RuleConfig):
    grid_size: int = GRID_SIZE
    max_turns: int = MAX_TURNS
    hero_hp: int = HERO_HP
    hero_dmg: int = HERO_DMG
    monster_hp: int = MONSTER_HP
    monster_dmg: int = MONSTER_DMG
    boss_hp: int = BOSS_HP
    boss_dmg: int = BOSS_DMG
    boss_level: int = BOSS_LEVEL
    potion_heal: int = POTION_HEAL
    spawn_chance: float = SPAWN_CHANCE
    xp_per_kill: int = XP_PER_KILL
    xp_level_up: int = XP_LEVEL_UP
    step_time_ms: int = 300
    # combat system
    hero_weapon: str = "rusty_sword"
    hero_traits: tuple[str, ...] = ("tough",)
    monster_weapons: tuple[str, ...] = ("claws", "fangs", "venom_sting")
    boss_weapon: str = "doom_axe"
    monster_skills: tuple[str, ...] = ("power_strike", "poison", "regenerate")
    boss_skills: tuple[str, ...] = ("doom_slam", "power_strike")
    max_traits: int = 3
    max_skills: int = 2
    hit_chance: float = 0.90        # base chance to land a hit
    crit_multiplier: float = 2.0    # crit damage multiplier
    level_dmg_bonus: int = 1        # +dmg per level above 1
    max_combat_rounds: int = 12     # rounds per encounter before hp ratio decides
    weapon_drop_chance: float = 0.5  # killed monster drops its weapon
    # level generator: requested difficulty 1-10, and the calibration of the
    # duel-threat measure (total expected hp fraction lost that maps to 10)
    difficulty: int = 5
    difficulty_reference: float = 2.0
    level_gen_attempts: int = 25
    weights: dict[str, int] = field(default_factory=lambda: {"monster": 70, "potion": 30})
    durations_s: dict[str, float | None] = field(default_factory=lambda: {"monster": None, "potion": None})
