"""Tests for the dungeon solver / playability prover: the expected-damage
duel model, A* optimality, real-game replay of solutions, and the
minimal-party-level proof."""

import random

from games.dungeon.combat import make_party, make_party_at_level
from games.dungeon.config import DungeonConfig
from games.dungeon.core import DungeonGame
from games.dungeon.levelgen import generate_level_with_target
from games.dungeon.solver import (
    _expected_duel,
    ensure_level_beatable,
    minimal_party_level,
    prove_playable,
    solve_level,
)


def _cfg(**kw):
    # no weapon drops in solver replays
    base = dict(weapon_drop_chance=0.0)
    base.update(kw)
    return DungeonConfig(**base)


def _flat_monster(x, y, hp, attack=0, ac=5, kind="monster", level=1):
    return {"name": "Boss" if kind == "boss" else "Monster", "x": x, "y": y, "kind": kind,
            "hp": hp, "max_hp": hp, "ac": ac, "attack": attack, "init": 2, "level": level,
            "weapon": {"name": "Claws", "die": 4, "bonus": 0}, "traits": [], "skills": []}


def test_expected_duel_model_party_strikes_with_combined_dps():
    cfg = DungeonConfig()
    party = make_party(cfg)
    # monster survives the party's first round: it strikes back (rounds-1)
    monster = _flat_monster(0, 0, hp=1000, attack=3)
    wins, hps = _expected_duel(party, monster, cfg)
    assert wins and sum(hps) < sum(m["hp"] for m in party), \
        "a monster that survives a round damages the party"
    # monster that dies in round 1 deals no damage
    weak = _flat_monster(0, 0, hp=1, attack=3)
    wins, hps = _expected_duel(party, weak, cfg)
    assert wins and list(hps) == [m["hp"] for m in party]
    # overwhelming monster wipes the party
    strong = _flat_monster(0, 0, hp=10_000, attack=100, ac=30)
    wins, hps = _expected_duel(party, strong, cfg)
    assert not wins and all(h <= 0 for h in hps)


def test_solver_solution_replays_as_a_win_in_the_real_game():
    cfg = _cfg()
    level = generate_level_with_target(random.Random(1), cfg, 4)
    party = make_party_at_level(cfg, 7)
    for m in party:
        m["x"], m["y"] = level["hero_start"]
    sol = solve_level(level, party, cfg, max_nodes=100_000)
    assert sol is not None and sol.turns == len(sol.moves)
    # replay the solution in the real core
    g = DungeonGame(rng=random.Random(1))
    g.init(cfg)
    s = g.state()
    s.monsters.clear()
    s.potions.clear()
    s.walls = [tuple(w) for w in level["walls"]]
    s.party = [dict(m) for m in make_party_at_level(cfg, 7)]
    for m in s.party:
        m["x"], m["y"] = level["hero_start"]
    for m in level["monsters"] + [level["boss"]]:
        m2 = dict(m)
        m2["skills"] = []
        s.monsters.append(m2)
    s.potions.extend(level["potions"])
    for mv in sol.moves:
        g.apply_action(0, {"direction": mv})
        g.tick()
    assert g.state().status == "won", "solver solution wins in the real game"


def test_solver_is_turn_optimal_on_a_straight_line():
    cfg = _cfg(grid_size=4)
    level = {"grid_size": 4, "difficulty": 1, "hero_start": (0, 0),
             "boss": _flat_monster(3, 3, hp=4, kind="boss", level=1),
             "monsters": [], "potions": [], "measured_difficulty": 1.0}
    party = make_party_at_level(cfg, 1)
    for m in party:
        m["x"], m["y"] = 0, 0
    sol = solve_level(level, party, cfg)
    assert sol is not None
    assert sol.turns == 6, "Manhattan distance 3+3 is the optimal (shortest) solution"
    assert sol.moves == ["right"] * 3 + ["down"] * 3


def test_unsolvable_level_returns_none():
    cfg = _cfg(grid_size=4)
    level = {"grid_size": 4, "difficulty": 10, "hero_start": (0, 0),
             "boss": _flat_monster(3, 3, hp=100_000, attack=100, ac=30, kind="boss", level=5),
             "monsters": [], "potions": [], "measured_difficulty": 10.0}
    party = make_party_at_level(cfg, 1)
    for m in party:
        m["x"], m["y"] = 0, 0
    assert solve_level(level, party, cfg, max_nodes=20_000) is None, \
        "no winning sequence exists against an unbeatable boss"


def test_prove_playable_reports_difficulty_and_party_level():
    # a level-10 boss makes difficulty 10 unprovable for a level-1 party
    cfg = _cfg(boss_level=10)
    low = prove_playable(10, 1, seed=2, cfg=cfg, max_nodes=100_000)
    assert low["playable"] is False and low["partyLevel"] == 1
    assert low["difficulty"] == 10 and 1 <= low["measuredDifficulty"] <= 10
    high = prove_playable(10, 8, seed=2, cfg=cfg, max_nodes=100_000)
    assert high["playable"] is True and high["turns"] == len(high["moves"])


def test_minimal_party_level_is_the_lowest_beatable_level():
    cfg = _cfg(boss_level=10)
    result = minimal_party_level(10, seed=2, cfg=cfg, max_nodes=100_000)
    assert result["playable"] and result["minimalPartyLevel"] == 2
    # the same generated level is used for every party level (same seed), and
    # party stats grow monotonically with level, so the level below the minimum
    # must be unprovable
    below = prove_playable(10, result["minimalPartyLevel"] - 1, seed=2, cfg=cfg, max_nodes=100_000)
    assert below["playable"] is False


def test_solver_routes_around_walls():
    cfg = _cfg(grid_size=4)
    level = {"grid_size": 4, "difficulty": 1, "hero_start": (0, 0),
             "boss": _flat_monster(3, 0, hp=4, kind="boss", level=1),
             "monsters": [], "potions": [], "measured_difficulty": 1.0,
             "walls": [(1, 0), (2, 0)]}  # the direct row to the boss is walled off
    party = make_party_at_level(cfg, 1)
    for m in party:
        m["x"], m["y"] = 0, 0
    sol = solve_level(level, party, cfg)
    assert sol is not None
    assert sol.turns == 5, "detour down-around-up beats the Manhattan distance of 3"
    assert sol.moves == ["down", "right", "right", "right", "up"]


def test_ensure_level_beatable_caps_an_unbeatable_boss():
    """A boss too strong for a fresh party is nerfed (level, then hp) until
    the solver can prove a winning solution — the level always stays beatable."""
    cfg = _cfg(grid_size=4)
    level = {"grid_size": 4, "difficulty": 10, "hero_start": (0, 0),
             "boss": _flat_monster(3, 3, hp=100_000, attack=100, ac=30, kind="boss", level=9),
             "monsters": [], "potions": [], "measured_difficulty": 10.0, "walls": []}
    before = (level["boss"]["level"], level["boss"]["max_hp"])
    ensure_level_beatable(random.Random(1), level, cfg, max_nodes=5_000)
    after = (level["boss"]["level"], level["boss"]["max_hp"])
    assert after < before, f"boss was nerfed: {before} -> {after}"
    party = make_party_at_level(cfg, 1)
    for m in party:
        m["x"], m["y"] = 0, 0
    sol = solve_level(level, party, cfg, max_nodes=50_000)
    assert sol is not None, "after the cap, a fresh party can provably win"


def test_generated_levels_are_always_beatable_by_a_fresh_party():
    cfg = _cfg()
    for d in (1, 5, 10):
        for seed in (1, 7, 42):
            level = generate_level_with_target(random.Random(seed), cfg, d)
            ensure_level_beatable(random.Random(seed), level, cfg, max_nodes=30_000)
            party = make_party_at_level(cfg, 1)
            for m in party:
                m["x"], m["y"] = level["hero_start"]
            assert solve_level(level, party, cfg, max_nodes=30_000) is not None, (d, seed)


def test_solver_is_deterministic_per_seed():
    cfg = _cfg()
    a = prove_playable(4, 7, seed=1, cfg=cfg, max_nodes=100_000)
    b = prove_playable(4, 7, seed=1, cfg=cfg, max_nodes=100_000)
    assert a["moves"] == b["moves"] and a["turns"] == b["turns"]
