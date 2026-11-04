"""Dungeon (party RPG) game tests: a party of classed heroes moves as a unit
and fights d20-vs-AC, initiative-ordered encounters. Level-generator tests
live in test_dungeon_levelgen.py. The shared contract suite in
tests/contracts/ also runs against it via the registry."""

import random

import pytest

from games.dungeon.combat import make_party, resolve_encounter, strike
from games.dungeon.config import DungeonConfig, xp_needed_for_level
from games.dungeon.core import DungeonGame

FISTS = {"name": "Fists", "die": 4, "bonus": 0}
CLAWS = {"name": "Claws", "die": 6, "bonus": 1}


class ScriptedRng:
    """Deterministic RNG for combat scripts: randint pops from `rands`
    (default: max of range), random pops from `randoms` (default 0.99, i.e.
    no dodge, no skill procs, no spawns, no weapon drops)."""

    def __init__(self, rands=(), randoms=()):
        self._rands = list(rands)
        self._randoms = list(randoms)

    def randint(self, a, b):
        return self._rands.pop(0) if self._rands else b

    def random(self):
        return self._randoms.pop(0) if self._randoms else 0.99

    def choice(self, seq):
        return seq[-1]

    def sample(self, seq, k):
        return list(seq)[:k]


def _cfg(**kw):
    base = dict(weapon_drop_chance=0.0)
    base.update(kw)
    return DungeonConfig(**base)


def _game(seed=1, **kw):
    g = DungeonGame(rng=random.Random(seed))
    g.init(_cfg(**kw))
    return g


def _open_field(g, rng=None):
    """Remove generated monsters/potions and pin the party at (0,0); optionally
    swap in a scripted RNG so the next tick's combat is fully deterministic."""
    s = g.state()
    s.monsters.clear()
    s.potions.clear()
    s.walls.clear()
    for m in s.party:
        m["x"], m["y"] = 0, 0
    if rng is not None:
        g._rng = rng
    return s


def _monster(x, y, hp, kind="monster", level=1, attack=3, ac=12, weapon=None, traits=None, skills=None):
    return {"name": "Boss" if kind == "boss" else "Monster", "x": x, "y": y, "kind": kind,
            "hp": hp, "max_hp": hp, "ac": ac, "attack": attack, "init": 2, "level": level,
            "weapon": weapon or dict(CLAWS), "traits": traits or [], "skills": skills or []}


def test_init_places_party_and_boss_in_opposite_corners():
    g = _game()
    s = g.state()
    n = s.grid_size
    corners = {(0, 0), (n - 1, 0), (0, n - 1), (n - 1, n - 1)}
    leader = s.party[0]
    assert (leader["x"], leader["y"]) in corners
    assert all((m["x"], m["y"]) == (leader["x"], leader["y"]) for m in s.party), \
        "the whole party shares the leader's cell"
    boss = next(m for m in s.monsters if m["kind"] == "boss")
    assert (boss["x"], boss["y"]) == (n - 1 - leader["x"], n - 1 - leader["y"])
    # party of three classed heroes with D&D-style stats
    assert [m["class"] for m in s.party] == ["warrior", "mage", "cleric"]
    warrior, mage, cleric = s.party
    assert warrior["hp"] == warrior["max_hp"] == 36  # 30 base + 6 from Tough
    assert warrior["ac"] == 16 and warrior["attack"] == 5 and warrior["weapon"]["name"] == "Iron Sword"
    assert mage["hp"] == 18 and mage["ac"] == 12 and mage["skills"], "mage carries a class skill"
    assert cleric["hp"] == 24 and cleric["ac"] == 14
    assert all(m["level"] == 1 and m["xp"] == 0 for m in s.party)
    assert s.party[0]["gold"] == 0, "the leader holds the party purse"
    # boss has AC/attack/dice too
    assert boss["level"] == 5 and boss["ac"] == 17 and boss["attack"] == 10
    assert boss["weapon"]["name"] == "Doom Axe" and boss["weapon"]["die"] == 12
    assert boss["skills"], "boss has skills"
    assert 1 <= s.difficulty <= 10 and 1 <= s.level_difficulty <= 10


def test_party_moves_together_with_direction():
    g = _game()
    _open_field(g)
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert all((m["x"], m["y"]) == (1, 0) for m in g.state().party)


def test_combat_kills_monster_and_grants_shared_loot():
    g = _game()
    # initiative rolls put the warrior first; its natural 20 crit one-shots
    # the monster (2d8+3 = 19 >= hp 4)
    rng = ScriptedRng(rands=[10, 9, 8, 1, 20, 8, 8], randoms=[0.99])
    s = _open_field(g, rng)
    s.monsters.append(_monster(1, 0, hp=4))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert all((m["x"], m["y"]) != (1, 0) for m in g.state().monsters)
    assert all(m["xp"] == 10 for m in g.state().party), "kill XP is shared by the whole party"
    assert g.state().party[0]["gold"] == 5
    assert g.state().score == 3 * 10 + 2 * 5
    assert any("slain" in line for line in g.state().combat_log), "combat log records the fight"


def test_monster_hits_back_and_focuses_the_weakest_member():
    g = _game()
    # monster wins initiative and strikes the mage (lowest hp) for 6+1=7;
    # then the party (11+7+9 = 27) brings the hp-25 monster down in round 1
    rng = ScriptedRng(rands=[1, 1, 1, 20, 15, 6, 10, 8, 10, 6, 10, 8],
                      randoms=[0.99] * 10)
    s = _open_field(g, rng)
    s.monsters.append(_monster(1, 0, hp=25))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    st = g.state()
    assert all((m["x"], m["y"]) != (1, 0) for m in st.monsters)
    mage = next(m for m in st.party if m["class"] == "mage")
    assert mage["hp"] == 18 - 7, "the monster focused the weakest member"
    assert any("hits Mage" in line for line in st.combat_log)


def test_natural_1_misses_and_natural_20_crits():
    cfg = _cfg()
    attacker = {"name": "Warrior", "hp": 30, "max_hp": 30, "ac": 16, "attack": 5,
                "level": 1, "weapon": dict(FISTS), "traits": [], "skills": []}
    defender = {"name": "M", "hp": 50, "max_hp": 50, "ac": 30, "traits": []}
    dmg, line = strike(ScriptedRng(rands=[1], randoms=[0.99]), attacker, defender, cfg)
    assert dmg == 0 and "misses" in line and defender["hp"] == 50, "natural 1 always misses"
    dmg, line = strike(ScriptedRng(rands=[20, 4, 4], randoms=[0.99]), attacker, defender, cfg)
    assert dmg == 8 and "crit" in line, "natural 20 always hits and doubles the dice (2d4 = 8)"


def test_armored_trait_reduces_damage_taken():
    cfg = _cfg()
    attacker = {"name": "M", "hp": 10, "max_hp": 10, "ac": 10, "attack": 5,
                "level": 1, "weapon": dict(CLAWS), "traits": [], "skills": []}
    defender = {"name": "Warrior", "hp": 30, "max_hp": 30, "ac": 10,
                "traits": [{"name": "Armored", "key": "armored", "max_hp": 0, "dr": 2,
                            "dodge": 0.0, "lifesteal": 0, "berserk": 0}]}
    dmg, _ = strike(ScriptedRng(rands=[15, 6], randoms=[0.99]), attacker, defender, cfg)
    assert dmg == 7 - 2 and defender["hp"] == 30 - 5


def test_skill_procs_and_multiplies_damage():
    cfg = _cfg()
    attacker = {"name": "M", "hp": 10, "max_hp": 10, "ac": 10, "attack": 5, "level": 1,
                "weapon": dict(FISTS), "traits": [],
                "skills": [{"name": "Power Strike", "chance": 1.0, "mult": 2.0}]}
    defender = {"name": "Hero", "hp": 50, "max_hp": 50, "ac": 10, "traits": []}
    dmg, line = strike(ScriptedRng(rands=[15, 4], randoms=[0.99, 0.0]), attacker, defender, cfg)
    assert dmg == 8 and defender["hp"] == 42  # 4 fists x2 = 8
    assert "Power Strike" in line


def test_dodge_trait_can_cause_a_miss():
    cfg = _cfg()
    attacker = {"name": "Hero", "hp": 10, "max_hp": 10, "ac": 10, "attack": 5, "level": 1,
                "weapon": dict(FISTS), "traits": [], "skills": []}
    defender = {"name": "M", "hp": 50, "max_hp": 50, "ac": 10,
                "traits": [{"name": "Nimble", "dodge": 1.0}]}
    dmg, line = strike(ScriptedRng(randoms=[0.0]), attacker, defender, cfg)
    assert dmg == 0 and "misses" in line and defender["hp"] == 50


def test_resolve_encounter_decides_the_winner():
    cfg = _cfg()
    party = make_party(cfg)
    for m in party:
        m["attack"] = 50  # always hit
    monster = _monster(0, 0, hp=10, ac=5)
    log = resolve_encounter(ScriptedRng(rands=[20, 20, 20, 1, 20, 8], randoms=[0.99] * 8),
                            party, monster, cfg)
    assert monster["hp"] <= 0 and all(m["hp"] > 0 for m in party)
    assert any("slain" in l for l in log)
    # and the other way round: a near-dead party against an overwhelming monster
    party2 = make_party(cfg)
    for m in party2:
        m["hp"] = 1
    monster2 = _monster(0, 0, hp=100_000, attack=50, ac=30)
    log2 = resolve_encounter(ScriptedRng(randoms=[0.99] * 40), party2, monster2, cfg)
    assert all(m["hp"] <= 0 for m in party2) and monster2["hp"] > 0
    assert any("falls" in l for l in log2)


def test_weapon_drop_goes_to_the_member_that_gains_most():
    g = _game(weapon_drop_chance=1.0)
    # warrior crit one-shots the hp-1 monster; the drop roll then succeeds
    rng = ScriptedRng(rands=[20, 1, 1, 1, 20, 8, 8], randoms=[0.99, 0.0, 0.99])
    s = _open_field(g, rng)
    fangs = {"name": "Fangs", "die": 8, "bonus": 2}
    s.monsters.append(_monster(1, 0, hp=1, weapon=fangs))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    party = g.state().party
    # fangs (6.5) beat the mage's staff (4.5) by the largest margin
    mage = next(m for m in party if m["class"] == "mage")
    assert mage["weapon"]["name"] == "Fangs", "the drop went to the member that gains most"
    assert party[0]["weapon"]["name"] == "Iron Sword", "the warrior keeps the better blade"


def test_level_up_grants_attack_hp_and_a_trait_to_every_member():
    g = _game()
    s = _open_field(g, ScriptedRng(randoms=[0.99]))
    for m in s.party:
        m["xp"] = 30  # one level-up worth, shared track
    g.apply_action(0, {"direction": "right"})
    g.tick()
    for m, base_attack, base_hp, base_traits in zip(g.state().party, (5, 4, 4), (36, 18, 24), (1, 0, 0)):
        assert m["level"] == 2 and m["xp"] == 0
        assert m["attack"] == base_attack + 1 and m["max_hp"] == base_hp + 6
        assert m["hp"] == m["max_hp"]
        assert len(m["traits"]) == base_traits + 1, "one new trait per member"


def test_level_is_static_after_generation():
    """The level is generated once at init; no monsters/potions spawn later."""
    g = DungeonGame(rng=random.Random(3))
    g.init(DungeonConfig())
    s = g.state()
    for m in s.party:
        m["hp"] = m["max_hp"] = 100000  # survive whatever we walk into
    before = (sorted((m["x"], m["y"], m["hp"]) for m in s.monsters),
              sorted(s.potions))
    dirs = ["left", "right", "up", "down"]
    for i in range(80):
        g.apply_action(0, {"direction": dirs[i % 4]})
        g.tick()
    st = g.state()
    after = (sorted((m["x"], m["y"], m["hp"]) for m in st.monsters),
             sorted(st.potions))
    assert st.status == "running"
    assert before == after, "the level stayed static for 80 ticks"


def test_each_new_level_needs_more_xp():
    cfg = _cfg()
    # geometric curve: 30, 45, 67, 101, ...
    assert xp_needed_for_level(1, cfg) == 30
    assert xp_needed_for_level(2, cfg) == 45
    assert xp_needed_for_level(3, cfg) == 67
    levels = [xp_needed_for_level(l, cfg) for l in range(1, 8)]
    assert levels == sorted(levels) and len(set(levels)) == len(levels), "strictly increasing"
    # in-game: 44 XP at level 2 is not enough, 45 XP levels up to 3
    g = _game()
    s = _open_field(g, ScriptedRng(randoms=[0.99]))
    for m in s.party:
        m["level"] = 2
        m["xp"] = 44
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert all(m["level"] == 2 and m["xp"] == 44 for m in g.state().party), "below the threshold"
    for m in g.state().party:
        m["xp"] = 45
    g.apply_action(0, {"direction": "down"})
    g.tick()
    assert all(m["level"] == 3 and m["xp"] == 0 for m in g.state().party), "exactly the threshold levels up"


def test_kill_logs_the_xp_gain():
    g = _game()
    rng = ScriptedRng(rands=[10, 9, 8, 1, 20, 8, 8], randoms=[0.99])
    s = _open_field(g, rng)
    s.monsters.append(_monster(1, 0, hp=4))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert any("+10 XP" in line for line in g.state().combat_log)


def test_no_input_means_no_movement_one_tile_per_command():
    """Movement is one tile per direction command; without input the party
    stands still (no snake-style auto-drift)."""
    g = _game()
    s = _open_field(g)
    for m in s.party:
        m["x"], m["y"] = 3, 3
    for _ in range(5):
        g.tick()
    assert all((m["x"], m["y"]) == (3, 3) for m in g.state().party)
    assert g.state().turn == 0, "idle ticks do not consume turns"
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert all((m["x"], m["y"]) == (4, 3) for m in g.state().party), "one command = one tile"
    assert g.state().turn == 1
    g.tick()
    assert all((m["x"], m["y"]) == (4, 3) for m in g.state().party), "no drift after the command"


def test_wall_blocks_the_move():
    g = _game()
    s = _open_field(g)
    s.walls.append((1, 0))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert all((m["x"], m["y"]) == (0, 0) for m in g.state().party), "wall blocks the move"
    assert g.state().turn == 0, "a blocked move consumes no turn"
    g.apply_action(0, {"direction": "down"})
    g.tick()
    assert all((m["x"], m["y"]) == (0, 1) for m in g.state().party), "other moves still work"


def test_each_command_moves_exactly_one_tile_and_allows_reversal():
    """The dungeon's own controls: every direction command is one tile
    (FIFO, no auto-repeat run-on), and a 180-degree turn is allowed —
    unlike snake's input queue, which rejects reversals."""
    g = _game()
    s = _open_field(g)
    for m in s.party:
        m["x"], m["y"] = 3, 3
    g.apply_action(0, {"direction": "left"})   # reversal of the initial facing (right)
    g.tick()
    assert all((m["x"], m["y"]) == (2, 3) for m in g.state().party), "reversal applied"
    g.apply_action(0, {"direction": "right"})
    g.apply_action(0, {"direction": "down"})   # queued: consumed one per tick
    g.tick()
    assert all((m["x"], m["y"]) == (3, 3) for m in g.state().party), "first queued command first"
    g.tick()
    assert all((m["x"], m["y"]) == (3, 4) for m in g.state().party), "second command on the next tick"
    g.tick()
    assert all((m["x"], m["y"]) == (3, 4) for m in g.state().party), "queue empty: stand still"


def test_potion_heals_the_whole_party():
    g = _game()
    s = _open_field(g, ScriptedRng(randoms=[0.99]))
    for m in s.party:
        m["hp"] = 5
    s.potions.append((1, 0))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert all(m["hp"] == 5 + 8 for m in g.state().party)
    assert (1, 0) not in g.state().potions


def test_party_wipe_is_terminal_and_stable():
    g = _game()
    rng = ScriptedRng(randoms=[0.99] * 40)
    s = _open_field(g, rng)
    for m in s.party:
        m["hp"] = 1
    s.monsters.append(_monster(1, 0, hp=100_000, attack=50, ac=30))
    g.apply_action(0, {"direction": "right"})
    g.tick()
    assert g.state().status == "dead"
    before = repr(g.state())
    g.tick()
    assert repr(g.state()) == before


def test_boss_kill_wins_and_pays_the_party_purse():
    g = _game()
    s = g.state()
    boss = next(m for m in s.monsters if m["kind"] == "boss")
    boss["hp"] = 1  # any hit slays it
    bx, by = boss["x"], boss["y"]
    for m in s.party:
        m["x"], m["y"] = (bx - 1, by) if bx > 0 else (bx, by - 1)
    g._rng = ScriptedRng(rands=[20, 1, 1, 1, 20, 8, 8], randoms=[0.99, 0.0, 0.99])
    g.apply_action(0, {"direction": "right" if bx > 0 else "down"})
    g.tick()
    assert g.state().status == "won"
    assert g.state().party[0]["gold"] == 25


def test_enchant_action_targets_a_chosen_member_and_spends_party_gold():
    g = _game()
    s = _open_field(g, ScriptedRng())
    s.party[0]["gold"] = 50
    g.apply_action(0, {"enchant": "frost", "member": 1})
    assert s.party[1]["weapon"]["enchant"]["school"] == "frost"
    assert s.party[0]["weapon"]["enchant"] is None, "only the chosen member's weapon"
    assert s.party[0]["gold"] == 40, "the leader's purse paid"
    assert any("enchant" in line.lower() for line in s.combat_log)
    with pytest.raises(ValueError):
        g.apply_action(0, {"enchant": "fire", "member": 99})
    with pytest.raises(ValueError):
        g.apply_action(0, {"enchant": "shadow"})


def test_single_player_rejects_player_1():
    g = _game()
    with pytest.raises(ValueError):
        g.apply_action(1, {"direction": "left"})
