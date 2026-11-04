"""Randomized dungeon level generator with a 1-10 difficulty target.

`generate_level` builds a randomized layout (party start corner, boss in the
diagonally opposite corner, monsters and potions on free cells) from a
continuous intensity in [0,1]. `measure_difficulty` independently scores a
layout against the party's stats: for every monster it estimates the fraction
of the party's effective HP the monster can deal before dying (duel threat,
capped at 1.0 = lethal), which is exactly "how close the monster's stats are
to the player's". `generate_level_with_target` searches intensities
(bounded attempts, seeded RNG keeps it deterministic) and returns the layout
whose measured difficulty is closest to the requested 1-10 target.
"""

from __future__ import annotations

import random

from .combat import make_monster, make_party
from .config import DungeonConfig

MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 10


def clamp_difficulty(difficulty: int) -> int:
    try:
        d = int(difficulty)
    except (TypeError, ValueError):
        return 5
    return min(MAX_DIFFICULTY, max(MIN_DIFFICULTY, d))


def generate_level(rng: random.Random, cfg: DungeonConfig, difficulty: int,
                   intensity: float | None = None) -> dict:
    """One randomized layout. `intensity` (0..1) drives monster count/level
    and potion scarcity; defaults to the linear mapping of `difficulty`."""
    n = cfg.grid_size
    d = clamp_difficulty(difficulty)
    x = (d - MIN_DIFFICULTY) / (MAX_DIFFICULTY - MIN_DIFFICULTY) if intensity is None else intensity
    x = min(1.0, max(0.0, x))
    corners = [(0, 0), (n - 1, 0), (0, n - 1), (n - 1, n - 1)]
    hero_cell = rng.choice(corners)
    boss_cell = (n - 1 - hero_cell[0], n - 1 - hero_cell[1])  # diagonal opposite
    occupied = {hero_cell, boss_cell}
    free = [(x_, y_) for x_ in range(n) for y_ in range(n) if (x_, y_) not in occupied]
    monster_count = 1 + round(x * (n - 2))   # 1 .. n-1 monsters
    potion_count = max(1, round(3 - 2 * x))   # more potions on easy layouts
    cells = rng.sample(free, monster_count + potion_count)
    monsters = []
    for i in range(monster_count):
        cx, cy = cells[i]
        level = min(5, 1 + round(x * 4) + rng.randint(0, 1))
        monsters.append(make_monster(rng, cx, cy, cfg, kind="monster", level=level))
    potions = [cells[monster_count + i] for i in range(potion_count)]
    return {
        "grid_size": n,
        "difficulty": d,
        "hero_start": hero_cell,
        "boss": make_monster(rng, boss_cell[0], boss_cell[1], cfg, kind="boss"),
        "monsters": monsters,
        "potions": potions,
    }


def hit_probability(attack: int, ac: int) -> float:
    """Chance that d20 + attack >= ac (natural 20 always hits, natural 1
    always misses), clamped to a small residual chance either way."""
    p = (21 + attack - ac) / 20.0
    return min(1.0, max(0.05, p))


def _dps(actor: dict, cfg: DungeonConfig, target_ac: int) -> float:
    """Expected damage per strike against a defender with the given AC: weapon
    die expectation + bonus + level scaling, times hit probability, plus the
    natural-20 extra (doubled dice) and expected skill bonus damage."""
    weapon = actor.get("weapon") or {}
    avg_hit = (weapon.get("die", 4) + 1) / 2 + weapon.get("bonus", 0) \
        + (actor.get("level", 1) - 1) * cfg.level_dmg_bonus
    # enchantment expectation: fire adds flat damage, storm adds double-hit chance
    ench = weapon.get("enchant") or {}
    elvl = ench.get("level", 0)
    if ench.get("school") == "fire":
        avg_hit += 2 * elvl
    elif ench.get("school") == "storm":
        avg_hit *= 1 + 0.15 * elvl
    hit_p = hit_probability(actor.get("attack", 0), target_ac)
    base = max(1.0, avg_hit)
    skill_bonus = sum(
        s.get("chance", 0) * (s.get("dmg", 0) + base * max(0.0, s.get("mult", 1.0) - 1))
        for s in actor.get("skills") or []
    )
    return hit_p * base * (1 + 1 / 20) + skill_bonus  # nat 20 doubles the dice


def _party_dps(party: list[dict], target_ac: int, cfg: DungeonConfig) -> float:
    return sum(_dps(m, cfg, target_ac) for m in party if m.get("hp", 0) > 0)


def _effective_hp(actor: dict) -> float:
    """max_hp adjusted for dodge (dodge removes incoming hits)."""
    dodge = min(0.75, sum(t.get("dodge", 0) for t in actor.get("traits") or []))
    return max(1.0, actor.get("max_hp", 1)) / max(0.05, 1.0 - dodge)


def _party_effective_hp(party: list[dict]) -> float:
    return sum(_effective_hp(m) for m in party if m.get("hp", 0) > 0)


def duel_threat(monster: dict, party: list[dict], cfg: DungeonConfig) -> float:
    """Expected fraction of the party's effective HP lost in a duel against
    this monster, capped at 1.0 (the monster can wipe the party outright).
    This is the core "how close are the monster's stats to the player's"."""
    avg_ac = sum(m.get("ac", 10) for m in party) / max(1, len(party))
    avg_dr = sum(sum(t.get("dr", 0) for t in m.get("traits") or []) for m in party) / max(1, len(party))
    party_dps = _party_dps(party, monster.get("ac", 12), cfg)
    mon_dps = max(1.0, _dps(monster, cfg, avg_ac) - avg_dr)
    rounds_to_kill = max(1.0, monster.get("max_hp", 1) / max(1.0, party_dps))
    return min(1.0, mon_dps * (rounds_to_kill - 1) / max(1.0, _party_effective_hp(party)))


def measure_difficulty(level: dict, party: list[dict], cfg: DungeonConfig) -> float:
    """Score a layout 1-10: mean monster duel threat amplified by monster
    count, plus a boss pressure term, minus potion relief."""
    monsters = level.get("monsters", [])
    threats = [duel_threat(m, party, cfg) for m in monsters]
    mean_threat = sum(threats) / len(threats) if threats else 0.0
    count_factor = len(monsters) / max(1, level["grid_size"] - 1)
    party_hp = max(1, sum(m.get("max_hp", 1) for m in party))
    potion_relief = min(0.3, 0.3 * cfg.potion_heal * len(level.get("potions", [])) / party_hp)
    boss_term = 0.1 * duel_threat(level["boss"], party, cfg)
    base = mean_threat * (0.5 + 0.5 * count_factor) + boss_term - potion_relief
    # difficulty_reference is the calibration knob: the duel-threat base value
    # that maps to difficulty 10
    score = MIN_DIFFICULTY + (MAX_DIFFICULTY - MIN_DIFFICULTY) * min(1.0, max(0.0, base / cfg.difficulty_reference))
    return round(min(MAX_DIFFICULTY, max(MIN_DIFFICULTY, score)), 2)


def generate_level_with_target(rng: random.Random, cfg: DungeonConfig, difficulty: int,
                               attempts: int | None = None) -> dict:
    """Search intensities and return the layout whose measured difficulty is
    closest to the requested target (early-exits within tolerance)."""
    d = clamp_difficulty(difficulty)
    attempts = max(1, attempts or cfg.level_gen_attempts)
    best: dict | None = None
    best_err = None
    for i in range(attempts):
        intensity = i / (attempts - 1) if attempts > 1 else (d - MIN_DIFFICULTY) / (MAX_DIFFICULTY - MIN_DIFFICULTY)
        cand = generate_level(rng, cfg, d, intensity=intensity)
        party = make_party(cfg)
        for member in party:
            member["x"], member["y"] = cand["hero_start"]
        cand["measured_difficulty"] = measure_difficulty(cand, party, cfg)
        err = abs(cand["measured_difficulty"] - d)
        if best is None or err < best_err:
            best, best_err = cand, err
        if best_err <= 0.5:
            break
    return best
