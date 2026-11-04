"""Tests for the dungeon solver / playability prover: the expected-damage
duel model, A* optimality, real-game replay of solutions, and the
minimal-hero-level proof."""

import random

from games.dungeon.combat import make_hero, make_hero_at_level
from games.dungeon.config import DungeonConfig
from games.dungeon.core import DungeonGame
from games.dungeon.levelgen import generate_level_with_target
from games.dungeon.solver import (
    _expected_duel,
    minimal_hero_level,
    prove_playable,
    solve_level,
)


def _cfg(**kw):
    # deterministic combat for replays: always hit, no crits, no spawns/drops
    base = dict(hit_chance=1.0, weapon_drop_chance=0.0, hero_weapon="fists",
                spawn_chance=0.0)
    base.update(kw)
    return DungeonConfig(**base)


def _flat_monster(x, y, hp, dmg=0, kind="monster", level=1):
    return {"name": "Boss" if kind == "boss" else "Monster", "x": x, "y": y, "kind": kind,
            "hp": hp, "max_hp": hp, "dmg": dmg, "level": level,
            "weapon": {"name": "Claws", "dmg": 0, "crit": 0.0}, "traits": [], "skills": []}


def test_expected_duel_model_hero_strikes_first():
    cfg = DungeonConfig()
    hero = make_hero(cfg)
    # monster survives two hero strikes: hero takes (rounds-1) monster hits
    monster = _flat_monster(0, 0, hp=12, dmg=3)
    monster["weapon"] = {"name": "Claws", "dmg": 1, "crit": 0.0}
    wins, hp_after = _expected_duel(hero, monster, cfg)
    assert wins and hp_after < hero["hp"], "monster that survives a round hits back"
    # monster that dies to the first strike deals no damage
    weak = _flat_monster(0, 0, hp=1, dmg=3)
    wins, hp_after = _expected_duel(hero, weak, cfg)
    assert wins and hp_after == hero["hp"]
    # overwhelming monster wins the duel
    strong = _flat_monster(0, 0, hp=10_000, dmg=100)
    wins, _ = _expected_duel(hero, strong, cfg)
    assert not wins


def test_solver_solution_replays_as_a_win_in_the_real_game():
    cfg = _cfg()
    level = generate_level_with_target(random.Random(1), cfg, 4)
    hero = make_hero_at_level(cfg, 7)
    hero["x"], hero["y"] = level["hero_start"]
    sol = solve_level(level, hero, cfg, max_nodes=100_000)
    assert sol is not None and sol.turns == len(sol.moves)
    # replay the solution in the real core with deterministic combat
    g = DungeonGame(rng=random.Random(1))
    g.init(cfg)
    s = g.state()
    s.monsters.clear()
    s.potions.clear()
    s.hero.update({k: hero[k] for k in ("hp", "max_hp", "dmg", "level", "xp",
                                        "weapon", "traits")})
    s.hero["x"], s.hero["y"] = level["hero_start"]
    for m in level["monsters"] + [level["boss"]]:
        m2 = dict(m)
        m2["skills"] = []
        m2["weapon"] = dict(m2["weapon"], crit=0.0)
        s.monsters.append(m2)
    s.potions.extend(level["potions"])
    for mv in sol.moves:
        g.apply_action(0, {"direction": mv})
        g.tick()
    assert g.state().status == "won", "solver solution wins in the real (deterministic) game"


def test_solver_is_turn_optimal_on_a_straight_line():
    cfg = _cfg(grid_size=4)
    level = {"grid_size": 4, "difficulty": 1, "hero_start": (0, 0),
             "boss": _flat_monster(3, 3, hp=4, dmg=0, kind="boss", level=1),
             "monsters": [], "potions": [], "measured_difficulty": 1.0}
    hero = make_hero_at_level(cfg, 1)
    hero["x"], hero["y"] = 0, 0
    sol = solve_level(level, hero, cfg)
    assert sol is not None
    assert sol.turns == 6, "Manhattan distance 3+3 is the optimal (shortest) solution"
    assert sol.moves == ["right"] * 3 + ["down"] * 3


def test_unsolvable_level_returns_none():
    cfg = _cfg(grid_size=4)
    level = {"grid_size": 4, "difficulty": 10, "hero_start": (0, 0),
             "boss": _flat_monster(3, 3, hp=100_000, dmg=100, kind="boss", level=5),
             "monsters": [], "potions": [], "measured_difficulty": 10.0}
    hero = make_hero_at_level(cfg, 1)
    hero["x"], hero["y"] = 0, 0
    assert solve_level(level, hero, cfg, max_nodes=20_000) is None, \
        "no winning sequence exists against an unbeatable boss"


def test_prove_playable_reports_difficulty_and_level():
    cfg = _cfg()
    low = prove_playable(5, 1, seed=2, cfg=cfg, max_nodes=100_000)
    assert low["playable"] is False and low["heroLevel"] == 1
    assert low["difficulty"] == 5 and 1 <= low["measuredDifficulty"] <= 10
    high = prove_playable(5, 6, seed=2, cfg=cfg, max_nodes=100_000)
    assert high["playable"] is True and high["turns"] == len(high["moves"])


def test_minimal_hero_level_is_the_lowest_beatable_level():
    cfg = _cfg()
    result = minimal_hero_level(5, seed=2, cfg=cfg, max_nodes=100_000)
    assert result["playable"] and result["minimalHeroLevel"] == 6
    # the same generated level is used for every hero level (same seed), and
    # hero stats grow monotonically with level, so level-1 below the minimum
    # must be unprovable
    below = prove_playable(5, result["minimalHeroLevel"] - 1, seed=2, cfg=cfg, max_nodes=100_000)
    assert below["playable"] is False


def test_solver_is_deterministic_per_seed():
    cfg = _cfg()
    a = prove_playable(4, 7, seed=1, cfg=cfg, max_nodes=100_000)
    b = prove_playable(4, 7, seed=1, cfg=cfg, max_nodes=100_000)
    assert a["moves"] == b["moves"] and a["turns"] == b["turns"]
