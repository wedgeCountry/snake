"""Dungeon (party RPG) rule configuration, incl. the combat system's data tables.

A simplified Baldur's Gate: a party of classed heroes (warrior/mage/cleric)
moves as a unit through a grid dungeon; combat is D&D-style — d20 attack roll
+ attack bonus vs armor class, damage dice from the weapon, initiative-ordered
rounds. Actors (party members + monsters) carry a weapon, traits and a level;
monsters also carry skills. All tables are plain data so state stays
JSON-serializable.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..engine import RuleConfig

GRID_SIZE = 8
MAX_TURNS = 200
MONSTER_HP = 8
MONSTER_AC = 12
MONSTER_ATTACK = 3
MONSTER_INIT = 2
BOSS_HP = 30
BOSS_AC = 15
BOSS_ATTACK = 6
BOSS_INIT = 4
BOSS_LEVEL = 5
POTION_HEAL = 8
XP_PER_KILL = 10
XP_LEVEL_UP = 30      # XP needed to go from level 1 to 2
XP_LEVEL_GROWTH = 1.5  # each new level needs xp_level_up * growth^(level-1) XP


def xp_needed_for_level(level: int, cfg: "DungeonConfig") -> int:
    """XP a member of the given level needs to reach the next level. Each new
    level costs more than the previous one (geometric curve)."""
    return int(cfg.xp_level_up * cfg.xp_level_growth ** max(0, level - 1))

# weapon key -> {name, damage die sides, flat damage bonus}
WEAPON_TABLE: dict[str, dict] = {
    "fists":         {"name": "Fists",          "die": 4,  "bonus": 0},
    "staff":         {"name": "Staff",          "die": 6,  "bonus": 1},
    "rusty_sword":   {"name": "Rusty Sword",    "die": 8,  "bonus": 1},
    "iron_sword":    {"name": "Iron Sword",     "die": 8,  "bonus": 3},
    "knights_blade": {"name": "Knight's Blade", "die": 10, "bonus": 4},
    "claws":         {"name": "Claws",          "die": 6,  "bonus": 1},
    "fangs":         {"name": "Fangs",          "die": 8,  "bonus": 2},
    "venom_sting":   {"name": "Venom Sting",    "die": 8,  "bonus": 3},
    "doom_axe":      {"name": "Doom Axe",       "die": 12, "bonus": 5},
}

# party class key -> base stats; the party is one member per listed class
PARTY_TABLE: dict[str, dict] = {
    "warrior": {"name": "Warrior", "hp": 30, "ac": 16, "attack": 5, "init": 2,
                "weapon": "iron_sword", "traits": ("tough",), "skills": ()},
    "mage":    {"name": "Mage",    "hp": 18, "ac": 12, "attack": 4, "init": 3,
                "weapon": "staff", "traits": (), "skills": ("power_strike",)},
    "cleric":  {"name": "Cleric",  "hp": 24, "ac": 14, "attack": 4, "init": 1,
                "weapon": "rusty_sword", "traits": (), "skills": ("regenerate",)},
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

# legendary weapon key -> weapon stats + a fixed starting enchantment
LEGENDARY_TABLE: dict[str, dict] = {
    "dragonfang":  {"name": "Dragonfang",  "die": 12, "bonus": 4,
                    "enchant": {"school": "fire",  "level": 1}},
    "frostmourne": {"name": "Frostmourne", "die": 10, "bonus": 4,
                    "enchant": {"school": "frost", "level": 1}},
    "bloodthirst": {"name": "Bloodthirst", "die": 10, "bonus": 3,
                    "enchant": {"school": "blood", "level": 1}},
    "stormcaller": {"name": "Stormcaller", "die": 10, "bonus": 4,
                    "enchant": {"school": "storm", "level": 1}},
}

# enchant school key -> combat effect, scaling per enchant level
# fire:  +2 damage per level on every hit
# frost: 10% per level chance to freeze the defender (it skips its next strike)
# blood: heal the attacker 1+level per hit
# storm: 15% per level chance to deal double damage on a hit
ENCHANT_TABLE: dict[str, dict] = {
    "fire":  {"name": "Immolation",   "dmg_per_level": 2},
    "frost": {"name": "Glacial",      "freeze_chance_per_level": 0.10},
    "blood": {"name": "Vampiric",     "heal_per_level": 1},
    "storm": {"name": "Stormforged",  "double_chance_per_level": 0.15},
}


@dataclass(frozen=True)
class DungeonConfig(RuleConfig):
    grid_size: int = GRID_SIZE
    max_turns: int = MAX_TURNS
    monster_hp: int = MONSTER_HP
    monster_ac: int = MONSTER_AC
    monster_attack: int = MONSTER_ATTACK
    monster_init: int = MONSTER_INIT
    boss_hp: int = BOSS_HP
    boss_ac: int = BOSS_AC
    boss_attack: int = BOSS_ATTACK
    boss_init: int = BOSS_INIT
    boss_level: int = BOSS_LEVEL
    potion_heal: int = POTION_HEAL
    xp_per_kill: int = XP_PER_KILL
    xp_level_up: int = XP_LEVEL_UP      # XP for level 1 -> 2 (base of the curve)
    xp_level_growth: float = XP_LEVEL_GROWTH  # per-level XP cost multiplier
    step_time_ms: int = 300
    # the party: one hero per class key, in this order (index 0 is the leader
    # and holds the party's gold purse and grid position)
    party_classes: tuple[str, ...] = ("warrior", "mage", "cleric")
    monster_weapons: tuple[str, ...] = ("claws", "fangs", "venom_sting")
    boss_weapon: str = "doom_axe"
    monster_skills: tuple[str, ...] = ("power_strike", "poison", "regenerate")
    boss_skills: tuple[str, ...] = ("doom_slam", "power_strike")
    max_traits: int = 3
    max_skills: int = 2
    # d20 combat: natural 1 always misses, natural 20 always hits and doubles
    # the damage dice; a hit needs d20 + attack >= defender AC
    level_dmg_bonus: int = 1        # +1 weapon damage per level above 1
    level_attack_bonus: int = 1     # +1 attack bonus per level above 1
    level_hp_bonus: int = 6         # +6 max hp per level above 1
    max_combat_rounds: int = 12     # rounds per encounter before hp ratio decides
    weapon_drop_chance: float = 0.5  # killed monster drops its weapon
    # level generator: requested difficulty 1-10, and the calibration of the
    # duel-threat measure (total expected hp fraction lost that maps to 10)
    difficulty: int = 5
    difficulty_reference: float = 0.2
    level_gen_attempts: int = 25
    # legendary objects & enchanting
    max_enchant_level: int = 3
    enchant_cost_base: int = 10   # gold cost = base * (new level); level 1 costs 10
    boss_legendary_drop: bool = True  # the boss always drops a legendary weapon
