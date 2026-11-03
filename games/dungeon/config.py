"""Dungeon (RPG) rule configuration."""

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
POTION_HEAL = 8
SPAWN_CHANCE = 0.35
XP_PER_KILL = 10
XP_LEVEL_UP = 30


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
    potion_heal: int = POTION_HEAL
    spawn_chance: float = SPAWN_CHANCE
    xp_per_kill: int = XP_PER_KILL
    xp_level_up: int = XP_LEVEL_UP
    step_time_ms: int = 300
    weights: dict[str, int] = field(default_factory=lambda: {"monster": 70, "potion": 30})
    durations_s: dict[str, float | None] = field(default_factory=lambda: {"monster": None, "potion": None})
