"""Dungeon core — a simplified Baldur's Gate: a party of classed heroes
(warrior/mage/cleric, each with hp, AC, attack bonus, weapon, traits, level)
moves as a unit through a grid dungeon, fights monsters in initiative-ordered
d20-vs-AC round combat, grabs potions (party-wide heal) and dropped weapons,
shares XP and levels up every member, and slay the boss in the far corner.
The level (monsters, potions, walls) is generated once at init and stays
static afterwards — no mid-game spawns — and the boss is capped so the level
is always provably beatable. Movement is one tile per command: no input means
the party stands still, direction input is last-write-wins (reversal allowed,
unlike snake's queue), and walls block moves. Zero I/O, injectable RNG.
Implements the pipeline Game protocol."""

from __future__ import annotations

import copy
import random
from typing import Any

from ..common.direction import Direction
from ..common.grid_move import clamp2d
from ..engine import GameState
from .combat import enchant_weapon, make_legendary, make_party, random_trait, resolve_encounter
from .config import LEGENDARY_TABLE, DungeonConfig, xp_needed_for_level
from .levelgen import generate_level_with_target
from .solver import ensure_level_beatable

COMBAT_LOG_LINES = 6


def _weapon_score(w: dict) -> float:
    return w.get("die", 4) / 2 + 0.5 + w.get("bonus", 0)


def _leader(state: "DungeonState") -> dict:
    return state.party[0]


class DungeonState(GameState):
    state_schema_version = 2

    def __init__(self, grid_size: int, party: list[dict], monsters: list[dict],
                 potions: list[tuple[int, int]], walls: list[tuple[int, int]],
                 score: int, turn: int, max_turns: int,
                 status: str = "running", step_time_ms: int = 300,
                 combat_log: list[str] | None = None, difficulty: int = 5,
                 level_difficulty: float = 5.0) -> None:
        self.grid_size = grid_size
        self.party = party  # [{name, class, x, y, hp, max_hp, ac, attack, init, level, xp, weapon, traits, skills}]
        self.monsters = monsters  # [{name, x, y, kind, hp, max_hp, ac, attack, init, level, weapon, traits, skills}]
        self.potions = list(potions)
        self.walls = list(walls)  # cells that block movement
        self.score = score
        self.turn = turn
        self.max_turns = max_turns
        self.status = status
        self.step_time_ms = step_time_ms
        self.combat_log = combat_log or []
        self.difficulty = difficulty            # requested level difficulty (1-10)
        self.level_difficulty = level_difficulty  # measured difficulty of the generated layout


class DungeonGame:
    def __init__(self, rng: random.Random | None = None,
                 config: DungeonConfig | None = None) -> None:
        self._rng = rng or random.Random()
        self._config = config or DungeonConfig()
        self._state: DungeonState | None = None
        self._last = Direction(1, 0, 0)   # drift direction when no input is queued
        self._next: Direction | None = None  # last-write-wins steering input

    @property
    def state_schema_version(self) -> int:
        return DungeonState.state_schema_version

    def init(self, config: Any = None) -> DungeonState:
        if isinstance(config, DungeonConfig):
            cfg = config
        else:
            step = getattr(config, "step_time_ms", None)
            cfg = DungeonConfig(step_time_ms=step) if isinstance(step, int) else self._config
        n = cfg.grid_size
        level = generate_level_with_target(self._rng, cfg, cfg.difficulty)
        level = ensure_level_beatable(self._rng, level, cfg)  # boss cap: always solvable
        party = make_party(cfg)
        for member in party:
            member["x"], member["y"] = level["hero_start"]
        self._state = DungeonState(n, party, [level["boss"]] + level["monsters"],
                                   list(level["potions"]), [tuple(w) for w in level["walls"]],
                                   0, 0, cfg.max_turns,
                                   step_time_ms=cfg.step_time_ms,
                                   difficulty=level["difficulty"],
                                   level_difficulty=level["measured_difficulty"])
        self._config = cfg
        self._last = Direction(1, 0, 0)
        self._next = None
        return self._state

    def state(self) -> DungeonState:
        if self._state is None:
            return self.init()
        return self._state

    def restore(self, data: dict) -> None:
        """Restore a savegame (wire-format state dict from the serializer)."""
        party = [copy.deepcopy(m) for m in data["party"]]
        monsters = [copy.deepcopy(m) for m in data.get("monsters", [])]
        potions = [tuple(p) for p in data.get("potions", [])]
        walls = [tuple(w) for w in data.get("walls", [])]
        self._state = DungeonState(
            int(data["gridSize"]), party, monsters, potions, walls,
            int(data.get("score", 0)), int(data.get("turn", 0)),
            int(data.get("maxTurns", self._config.max_turns)),
            status=str(data.get("status", "running")),
            step_time_ms=int(data.get("stepTimeMs", self._config.step_time_ms)),
            combat_log=list(data.get("combatLog", [])),
            difficulty=int(data.get("difficulty", 5)),
            level_difficulty=float(data.get("levelDifficulty", 5.0)),
        )
        self._last = Direction(1, 0, 0)
        self._next = None

    def max_players(self) -> int:
        return 1

    def is_terminal(self) -> bool:
        return self.state().status != "running"

    def apply_action(self, player: int, action: dict[str, Any]) -> None:
        if player != 0:
            raise ValueError("dungeon is single-player")
        if "direction" in action:
            # the dungeon's own controls: last write wins, 180-degree turns
            # allowed (unlike snake's input queue)
            self._next = Direction.from_name_2d(str(action["direction"]))
        elif "enchant" in action:
            state = self.state()
            idx = int(action.get("member", 0))
            if not 0 <= idx < len(state.party):
                raise ValueError(f"no party member {idx}")
            ok, msg = enchant_weapon(state.party[idx], self._config,
                                     str(action["enchant"]) or None, purse=_leader(state))
            if not ok:
                raise ValueError(msg)
            state.combat_log = (state.combat_log + [msg])[-COMBAT_LOG_LINES:]
        else:
            raise ValueError(f"unknown action: {sorted(action)}")

    def tick(self) -> DungeonState:
        state = self.state()
        if state.status != "running":
            return state
        if self._next is None:
            return state  # one tile per command: no input, no movement
        cfg = self._config
        d = self._next
        self._next = None
        self._last = d
        dx, dy = d.as_2d()
        n = state.grid_size
        leader = _leader(state)
        nx, ny = clamp2d(leader["x"] + dx, leader["y"] + dy, n)
        if (nx, ny) in state.walls:
            return state  # walls block the move; no turn consumed
        for member in state.party:
            member["x"], member["y"] = nx, ny
        state.turn += 1
        self._combat(state, cfg)
        self._loot(state, cfg)
        self._level_up(state, cfg)
        state.score = sum(m["xp"] for m in state.party) + 2 * leader.get("gold", 0)
        if all(m["hp"] <= 0 for m in state.party):
            state.status = "dead"
        elif state.turn >= state.max_turns:
            state.status = "dead"
        return state

    def _combat(self, state: DungeonState, cfg: DungeonConfig) -> None:
        leader = _leader(state)
        cell = (leader["x"], leader["y"])
        monster = next((m for m in state.monsters if (m["x"], m["y"]) == cell), None)
        if monster is None:
            return
        log = resolve_encounter(self._rng, state.party, monster, cfg)
        if monster["hp"] <= 0:
            state.monsters.remove(monster)
            if monster["kind"] == "boss":
                state.status = "won"
                leader["gold"] = leader.get("gold", 0) + 25
            else:
                for member in state.party:
                    member["xp"] += cfg.xp_per_kill
                leader["gold"] = leader.get("gold", 0) + 5
                log.append(f"+{cfg.xp_per_kill} XP for the whole party")
            self._maybe_take_weapon(state, monster, cfg, log)
        state.combat_log = log[-COMBAT_LOG_LINES:]
        for m in state.monsters:
            m.pop("frozen", None)
        for member in state.party:
            member.pop("frozen", None)

    def _maybe_take_weapon(self, state: DungeonState, monster: dict, cfg: DungeonConfig, log: list[str]) -> None:
        if monster.get("kind") == "boss" and cfg.boss_legendary_drop:
            drop = make_legendary(self._rng)  # bosses always drop a legendary object
        else:
            if self._rng.random() >= cfg.weapon_drop_chance:
                return
            drop = monster.get("weapon") or {}
        # the dropped weapon goes to the member whose current weapon improves most
        best_member, best_gain = None, 0.0
        for member in state.party:
            gain = _weapon_score(drop) - _weapon_score(member.get("weapon") or {})
            if gain > best_gain:
                best_member, best_gain = member, gain
        if best_member is not None:
            best_member["weapon"] = dict(drop)
            label = "legendary " if drop.get("key") in LEGENDARY_TABLE else ""
            log.append(f"{best_member['name']} takes the {label}{drop['name']}!")

    def _loot(self, state: DungeonState, cfg: DungeonConfig) -> None:
        leader = _leader(state)
        cell = (leader["x"], leader["y"])
        if cell in state.potions:
            state.potions.remove(cell)
            for member in state.party:
                member["hp"] = min(member["max_hp"], member["hp"] + cfg.potion_heal)

    def _level_up(self, state: DungeonState, cfg: DungeonConfig) -> None:
        for member in state.party:
            while member["xp"] >= xp_needed_for_level(member["level"], cfg) and state.status == "running":
                member["xp"] -= xp_needed_for_level(member["level"], cfg)
                member["level"] += 1
                member["attack"] += cfg.level_attack_bonus
                member["max_hp"] += cfg.level_hp_bonus
                trait = random_trait(self._rng, [t.get("key", t["name"]) for t in member["traits"]], cfg)
                if trait is not None:
                    member["traits"].append(trait)
                    member["max_hp"] += trait.get("max_hp", 0)
                member["hp"] = member["max_hp"]


