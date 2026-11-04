"""Optimal solver / playability prover for the party dungeon crawler.

`solve_level` runs A* (unit cost per turn, admissible heuristic = Manhattan
distance to the boss) over the full game state — party cell, every member's
hp, party level, xp, every monster's hp, remaining potions — so the returned
solution is a shortest (turn-optimal) winning move sequence. Duels are
resolved with a deterministic expected-damage model (`_expected_duel`: the
party's combined dps vs the monster, the monster striking back once per round
against the weakest member until it dies), and weapon drops are not assumed,
i.e. the proof covers the static generated layout conservatively.

`prove_playable(difficulty, party_level, ...)` generates a level and asks
whether a party of that level can beat it; `minimal_party_level` finds the
lowest party level x for which the answer is yes.
"""

from __future__ import annotations

import heapq
import math
import random
from dataclasses import dataclass

from .combat import make_monster, make_party_at_level
from .config import DungeonConfig, xp_needed_for_level
from .levelgen import _dps, generate_level_with_target, hit_probability

DIRS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
INITIAL_LAST = "right"  # the core's initial facing (kept in the search state)


@dataclass
class Solution:
    moves: list[str]
    turns: int
    party_level: int
    measured_difficulty: float


def _expected_duel(party: list[dict], monster: dict, cfg: DungeonConfig) -> tuple[bool, tuple[float, ...]]:
    """Deterministic duel: expected damage per strike on both sides; the party
    strikes with its combined dps, the monster strikes back once per round
    (focused on the weakest member) only while alive. Returns (party_wins,
    per-member hp after the duel, aligned with the party order)."""
    alive = [i for i, m in enumerate(party) if m["hp"] > 0]
    if not alive:
        return False, tuple(min(m["hp"], 0) for m in party)
    party_dps = sum(_dps(party[i], cfg, monster.get("ac", 12)) for i in alive)
    if party_dps <= 0:
        return False, tuple(min(m["hp"], 0) for m in party)
    avg_ac = sum(party[i].get("ac", 10) for i in alive) / len(alive)
    avg_dr = sum(sum(t.get("dr", 0) for t in party[i].get("traits") or []) for i in alive) / len(alive)
    mon_dps = max(1.0, _dps(monster, cfg, avg_ac) - avg_dr)
    rounds_to_kill = max(1, math.ceil(monster["max_hp"] / party_dps - 1e-9))
    dmg_taken = mon_dps * (rounds_to_kill - 1)
    hps = [float(m["hp"]) for m in party]
    # the monster focuses the weakest living member first
    for i in sorted(alive, key=lambda j: hps[j]):
        dealt = min(hps[i], dmg_taken)
        hps[i] -= dealt
        dmg_taken -= dealt
        if dmg_taken <= 0:
            break
    wins = any(h > 0 for h in hps)
    return wins, tuple(round(h, 2) for h in hps)


def _apply_level_ups(hps: tuple[float, ...], level: int, xp: int,
                     cfg: DungeonConfig) -> tuple[tuple[float, ...], int, int]:
    """Mirror of the core's level-up (all members share xp, so they share the
    level, with the scaling XP curve): on level-up every member is fully
    healed to its new max_hp."""
    while xp >= xp_needed_for_level(level, cfg):
        xp -= xp_needed_for_level(level, cfg)
        level += 1
        fresh = make_party_at_level(cfg, level)
        hps = tuple(float(m["max_hp"]) for m in fresh)
    return hps, level, xp


def _key(state) -> tuple:
    x, y, hps, level, xp, mons, pots, boss_dead, last = state
    return (x, y, hps, level, xp, mons, pots, boss_dead, last)


def solve_level(level: dict, party: list[dict], cfg: DungeonConfig,
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
    walls = frozenset(level.get("walls", ()))
    start_party = [dict(m) for m in party]
    for m in start_party:
        m["x"], m["y"] = level["hero_start"]
    start = (
        start_party[0]["x"], start_party[0]["y"],
        tuple(round(m["hp"], 2) for m in start_party),
        start_party[0]["level"], start_party[0]["xp"],
        frozenset((m["id"], round(m["hp"], 2)) for m in all_monsters),
        potions0, False, INITIAL_LAST,
    )

    def expand(state):
        x, y, hps, level_, xp, mons, pots, boss_dead, last = state
        # party view for this node (weapons/traits never change in the solver:
        # no weapon drops are assumed, traits come from level-ups only)
        pview = make_party_at_level(cfg, level_)
        for m, hp in zip(pview, hps):
            m["hp"] = hp
            m["x"], m["y"] = x, y
        for name, (dx, dy) in DIRS.items():
            nx, ny = min(max(x + dx, 0), n - 1), min(max(y + dy, 0), n - 1)
            if (nx, ny) in walls:
                continue  # walls block the move
            nhps, nlevel, nxp = hps, level_, xp
            nmons = set(mons)
            nBoss = boss_dead
            mid = cell_to_id.get((nx, ny))
            mhp = next((h for i, h in mons if i == mid), None)
            if mid is not None and mhp is not None:
                m = next(mm for mm in all_monsters if mm["id"] == mid)
                mview = dict(m, hp=mhp)
                view = [dict(mm, hp=hh) for mm, hh in zip(pview, nhps)]
                wins, nhps = _expected_duel(view, mview, cfg)
                if not wins:
                    continue
                nmons.discard((mid, mhp))
                if mid == boss_id:
                    nBoss = True
                else:
                    nxp += cfg.xp_per_kill
            npots = pots
            if (nx, ny) in pots:
                npots = pots - {(nx, ny)}
                fresh = make_party_at_level(cfg, nlevel)
                nhps = tuple(min(f["max_hp"], h + cfg.potion_heal) for f, h in zip(fresh, nhps))
            nhps, nlevel, nxp = _apply_level_ups(nhps, nlevel, nxp, cfg)
            yield (name, (nx, ny, nhps, nlevel, nxp, frozenset(nmons), npots, nBoss, name))

    def h(state):
        return abs(state[0] - boss_pos[0]) + abs(state[1] - boss_pos[1])

    counter = 0
    heap = [(h(start), 0, counter, start, [])]
    best = {_key(start): 0}
    nodes = 0
    while heap:
        _, turns, _, state, moves = heapq.heappop(heap)
        if state[7]:  # boss dead (boss_dead flag)
            return Solution(moves=moves, turns=turns, party_level=party[0]["level"],
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


def prove_playable(difficulty: int, party_level: int, seed: int = 1,
                   cfg: DungeonConfig | None = None, max_nodes: int = 200_000) -> dict:
    """Generate a level at the given difficulty and prove whether a party of
    `party_level` can beat it with optimal play (expected-damage duels)."""
    cfg = cfg or DungeonConfig()
    level = generate_level_with_target(random.Random(seed), cfg, difficulty)
    party = make_party_at_level(cfg, party_level)
    for m in party:
        m["x"], m["y"] = level["hero_start"]
    sol = solve_level(level, party, cfg, max_nodes=max_nodes)
    return {
        "difficulty": level["difficulty"],
        "measuredDifficulty": level["measured_difficulty"],
        "partyLevel": party_level,
        "playable": sol is not None,
        "turns": sol.turns if sol else None,
        "moves": sol.moves if sol else [],
    }


def ensure_level_beatable(rng: random.Random, level: dict, cfg: DungeonConfig,
                          party_level: int = 1, max_nodes: int = 50_000,
                          max_nerfs: int = 8) -> dict:
    """Cap the boss strength until a fresh party can provably beat the whole
    level: run the solver, and if no winning solution is found within the node
    budget, nerf the boss one level (halving its hp once it is at level 1).
    After this returns, the generated dungeon is guaranteed to have a solution
    (or the nerf budget was exhausted, which in practice means the boss was
    already beatable but the search budget ran out)."""
    for _ in range(max_nerfs):
        party = make_party_at_level(cfg, party_level)
        if solve_level(level, party, cfg, max_nodes=max_nodes) is not None:
            return level
        boss = level["boss"]
        if boss.get("level", 1) > 1:
            level["boss"] = make_monster(rng, boss["x"], boss["y"], cfg,
                                         kind="boss", level=boss["level"] - 1)
        else:
            boss["max_hp"] = max(1, boss["max_hp"] // 2)
            boss["hp"] = boss["max_hp"]
    return level


def minimal_party_level(difficulty: int, seed: int = 1, cfg: DungeonConfig | None = None,
                        max_level: int = 10, max_nodes: int = 200_000) -> dict:
    """The lowest party level x (1..max_level) that can beat the level, i.e.
    the smallest x for which the level is provably playable."""
    cfg = cfg or DungeonConfig()
    for lvl in range(1, max_level + 1):
        result = prove_playable(difficulty, lvl, seed=seed, cfg=cfg, max_nodes=max_nodes)
        if result["playable"]:
            result["minimalPartyLevel"] = lvl
            return result
    return {"difficulty": difficulty, "playable": False, "minimalPartyLevel": None}
