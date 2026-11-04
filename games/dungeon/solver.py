"""Optimal solver / playability prover for Dungeon Quest.

`solve_level` runs A* (unit cost per turn, admissible heuristic = Manhattan
distance to the boss) over the full game state — hero cell, hp, level, xp,
weapon, traits, every monster's hp, remaining potions — so the returned
solution is a shortest (turn-optimal) winning move sequence. Duels are
resolved with a deterministic expected-damage model (`_expected_duel`: the
hero strikes first each round, the monster only while alive), random spawns
are off and weapon drops are not assumed, i.e. the proof covers the static
generated layout conservatively.

`prove_playable(difficulty, hero_level, ...)` generates a level and asks
whether a hero of that level can beat it; `minimal_hero_level` finds the
lowest hero level x for which the answer is yes.
"""

from __future__ import annotations

import heapq
import math
import random
from dataclasses import dataclass, field

from .combat import make_hero_at_level
from .config import DungeonConfig, TRAIT_TABLE
from .levelgen import _dps, generate_level_with_target

DIRS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
OPPOSITE = {"left": "right", "right": "left", "up": "down", "down": "up"}
INITIAL_LAST = "right"  # the core's default drift direction


@dataclass
class Solution:
    moves: list[str]
    turns: int
    hero_level: int
    measured_difficulty: float


def _expected_duel(hero: dict, monster: dict, cfg: DungeonConfig) -> tuple[bool, float]:
    """Deterministic duel: expected damage per strike on both sides; the hero
    strikes first each round, the monster strikes back only while alive.
    Returns (hero_wins, hero_hp_after)."""
    hero_dps = _dps(hero, cfg)
    hero_dr = sum(t.get("dr", 0) for t in hero.get("traits") or [])
    mon_dps = max(1.0, _dps(monster, cfg) - hero_dr)
    rounds_to_kill = max(1, math.ceil(monster["max_hp"] / hero_dps - 1e-9))
    dmg_taken = mon_dps * (rounds_to_kill - 1)
    if dmg_taken >= hero["hp"]:
        return False, 0.0
    return True, round(hero["hp"] - dmg_taken, 2)


def _apply_level_ups(hero: dict, cfg: DungeonConfig) -> None:
    owned = [t.get("key", t["name"]) for t in hero["traits"]]
    while hero["xp"] >= cfg.xp_level_up:
        hero["xp"] -= cfg.xp_level_up
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


def _key(state) -> tuple:
    hx, hy, hp, level, xp, wkey, tkeys, mons, pots, boss_dead, last = state
    return (hx, hy, round(hp, 2), level, xp, wkey, tkeys, mons, pots, boss_dead, last)


def solve_level(level: dict, hero: dict, cfg: DungeonConfig,
                max_nodes: int = 200_000) -> Solution | None:
    """A* search for a shortest winning move sequence on the given layout.
    Returns None when no winning sequence exists within the node budget
    (budget exhaustion means "no proof found", not "unsolvable")."""
    n = level["grid_size"]
    monsters = [dict(m, id=i) for i, m in enumerate(level["monsters"])]
    boss = dict(level["boss"], id=len(monsters))
    all_monsters = monsters + [boss]
    cell_to_id = {(m["x"], m["y"]): m["id"] for m in all_monsters}
    boss_id = boss["id"]
    boss_pos = (boss["x"], boss["y"])
    potions0 = frozenset(level["potions"])
    start_hero = dict(hero)
    start_hero["x"], start_hero["y"] = level["hero_start"]
    start = (
        start_hero["x"], start_hero["y"], round(start_hero["hp"], 2), start_hero["level"],
        start_hero["xp"], start_hero["weapon"].get("key", start_hero["weapon"]["name"]),
        frozenset(t.get("key", t["name"]) for t in start_hero["traits"]),
        frozenset((m["id"], round(m["hp"], 2)) for m in all_monsters),
        potions0, False, INITIAL_LAST,
    )

    def expand(state):
        hx, hy, hp, level_, xp, wkey, tkeys, mons, pots, boss_dead, last = state
        # hero view for this level (weapon/traits never change in the solver:
        # no weapon drops are assumed, traits come from level-ups only)
        hview = dict(make_hero_at_level(cfg, level_), x=hx, y=hy, hp=hp, xp=xp)
        for name, (dx, dy) in DIRS.items():
            if name == OPPOSITE[last]:
                continue  # the input queue rejects 180-degree turns
            nx, ny = min(max(hx + dx, 0), n - 1), min(max(hy + dy, 0), n - 1)
            nhp, nlevel, nxp = hp, level_, xp
            nmons = set(mons)
            nBoss = boss_dead
            mid = cell_to_id.get((nx, ny))
            mhp = next((h for i, h in mons if i == mid), None)
            if mid is not None and mhp is not None:
                m = next(mm for mm in all_monsters if mm["id"] == mid)
                mview = dict(m, hp=mhp)
                wins, hp_after = _expected_duel(hview, mview, cfg)
                if not wins:
                    continue
                nhp = hp_after
                nmons.discard((mid, mhp))
                if mid == boss_id:
                    nBoss = True
                else:
                    nxp += cfg.xp_per_kill
            npots = pots
            if (nx, ny) in pots:
                npots = pots - {(nx, ny)}
                nhp = min(hview["max_hp"], nhp + cfg.potion_heal)
            nhero = dict(hview, hp=nhp, xp=nxp)
            _apply_level_ups(nhero, cfg)
            yield (name, (nx, ny, round(nhero["hp"], 2), nhero["level"], nhero["xp"],
                          wkey, tkeys, frozenset(nmons), npots, nBoss, name))

    def h(state):
        return abs(state[0] - boss_pos[0]) + abs(state[1] - boss_pos[1])

    counter = 0
    heap = [(h(start), 0, counter, start, [])]
    best = {_key(start): 0}
    nodes = 0
    while heap:
        _, turns, _, state, moves = heapq.heappop(heap)
        if state[9]:  # boss dead (boss_dead flag)
            return Solution(moves=moves, turns=turns, hero_level=hero["level"],
                            measured_difficulty=level.get("measured_difficulty", 0.0))
        if turns >= cfg.max_turns:
            continue
        k = _key(state)
        if best.get(k, 1e18) < turns:
            continue
        nodes += 1
        if nodes > max_nodes:
            return None
        for name, nstate in expand(state):
            nk = _key(nstate)
            nt = turns + 1
            if best.get(nk, 1e18) <= nt:
                continue
            best[nk] = nt
            counter += 1
            heapq.heappush(heap, (nt + h(nstate), nt, counter, nstate, moves + [name]))
    return None


def prove_playable(difficulty: int, hero_level: int, seed: int = 1,
                   cfg: DungeonConfig | None = None, max_nodes: int = 200_000) -> dict:
    """Generate a level at the given difficulty and prove whether a hero of
    `hero_level` can beat it with optimal play (expected-damage duels)."""
    cfg = cfg or DungeonConfig()
    level = generate_level_with_target(random.Random(seed), cfg, difficulty)
    hero = make_hero_at_level(cfg, hero_level)
    hero["x"], hero["y"] = level["hero_start"]
    sol = solve_level(level, hero, cfg, max_nodes=max_nodes)
    return {
        "difficulty": level["difficulty"],
        "measuredDifficulty": level["measured_difficulty"],
        "heroLevel": hero_level,
        "playable": sol is not None,
        "turns": sol.turns if sol else None,
        "moves": sol.moves if sol else [],
    }


def minimal_hero_level(difficulty: int, seed: int = 1, cfg: DungeonConfig | None = None,
                       max_level: int = 10, max_nodes: int = 200_000) -> dict:
    """The lowest hero level x (1..max_level) that can beat the level, i.e.
    the smallest x for which the level is provably playable."""
    cfg = cfg or DungeonConfig()
    for lvl in range(1, max_level + 1):
        result = prove_playable(difficulty, lvl, seed=seed, cfg=cfg, max_nodes=max_nodes)
        if result["playable"]:
            result["minimalHeroLevel"] = lvl
            return result
    return {"difficulty": difficulty, "playable": False, "minimalHeroLevel": None}
