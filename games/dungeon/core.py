"""Dungeon core — a pure single-player RPG: guide a hero (weapon, traits,
levels) through a grid dungeon, fight monsters (weapons, traits, levels,
skills) in round-based combat, grab potions and dropped weapons, level up,
and slay the boss in the far corner. Zero I/O, injectable RNG. Implements
the pipeline Game protocol."""

from __future__ import annotations

import copy
import random
from typing import Any

from ..common.direction import Direction, DirectionQueue
from ..common.grid_move import clamp2d
from ..common.spawner import WeightedSpawner
from ..engine import GameState
from .combat import enchant_weapon, make_hero, make_legendary, make_monster, random_trait, resolve_encounter
from .config import LEGENDARY_TABLE, DungeonConfig
from .levelgen import clamp_difficulty, generate_level_with_target

COMBAT_LOG_LINES = 6


def _weapon_score(w: dict) -> float:
    return w.get("dmg", 0) * 2 + w.get("crit", 0.0) * 10


class DungeonState(GameState):
    state_schema_version = 1

    def __init__(self, grid_size: int, hero: dict, monsters: list[dict],
                 potions: list[tuple[int, int]], score: int, turn: int, max_turns: int,
                 status: str = "running", step_time_ms: int = 300,
                 combat_log: list[str] | None = None, difficulty: int = 5,
                 level_difficulty: float = 5.0) -> None:
        self.grid_size = grid_size
        self.hero = hero  # {name, x, y, hp, max_hp, dmg, level, xp, gold, weapon, traits, skills}
        self.monsters = monsters  # [{name, x, y, hp, max_hp, dmg, level, kind, weapon, traits, skills}]
        self.potions = list(potions)
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
        self._queue = DirectionQueue()
        self._last = Direction(1, 0, 0)
        self._spawner = WeightedSpawner(self._rng, [("monster", 70), ("potion", 30)])

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
        hero = make_hero(cfg)
        hero["x"], hero["y"] = level["hero_start"]
        self._state = DungeonState(n, hero, [level["boss"]] + level["monsters"],
                                   list(level["potions"]), 0, 0, cfg.max_turns,
                                   step_time_ms=cfg.step_time_ms,
                                   difficulty=level["difficulty"],
                                   level_difficulty=level["measured_difficulty"])
        self._config = cfg
        self._queue.clear()
        self._last = Direction(1, 0, 0)
        return self._state

    def state(self) -> DungeonState:
        if self._state is None:
            return self.init()
        return self._state

    def restore(self, data: dict) -> None:
        """Restore a savegame (wire-format state dict from the serializer)."""
        hero = copy.deepcopy(data["hero"])
        monsters = [copy.deepcopy(m) for m in data.get("monsters", [])]
        potions = [tuple(p) for p in data.get("potions", [])]
        self._state = DungeonState(
            int(data["gridSize"]), hero, monsters, potions,
            int(data.get("score", 0)), int(data.get("turn", 0)),
            int(data.get("maxTurns", self._config.max_turns)),
            status=str(data.get("status", "running")),
            step_time_ms=int(data.get("stepTimeMs", self._config.step_time_ms)),
            combat_log=list(data.get("combatLog", [])),
            difficulty=int(data.get("difficulty", 5)),
            level_difficulty=float(data.get("levelDifficulty", 5.0)),
        )
        self._queue.clear()
        self._last = Direction(1, 0, 0)

    def max_players(self) -> int:
        return 1

    def is_terminal(self) -> bool:
        return self.state().status != "running"

    def apply_action(self, player: int, action: dict[str, Any]) -> None:
        if player != 0:
            raise ValueError("dungeon is single-player")
        if "direction" in action:
            direction = Direction.from_name_2d(str(action["direction"]))
            self._queue.push(direction, self._last)
        elif "enchant" in action:
            school = str(action["enchant"]) or None
            ok, msg = enchant_weapon(self.state().hero, self._config, school)
            if not ok:
                raise ValueError(msg)
            self.state().combat_log = (self.state().combat_log + [msg])[-COMBAT_LOG_LINES:]
        else:
            raise ValueError(f"unknown action: {sorted(action)}")

    def tick(self) -> DungeonState:
        state = self.state()
        if state.status != "running":
            return state
        cfg = self._config
        state.turn += 1
        n = state.grid_size
        d = self._queue.pop() or self._last
        self._last = d
        dx, dy = d.as_2d()
        hero = state.hero
        hero["x"], hero["y"] = clamp2d(hero["x"] + dx, hero["y"] + dy, n)
        self._combat(state, cfg)
        self._loot(state, cfg)
        self._maybe_spawn(state, cfg)
        self._level_up(state, cfg)
        state.score = hero["xp"] + 2 * hero["gold"]
        if hero["hp"] <= 0:
            state.status = "dead"
        elif state.turn >= state.max_turns:
            state.status = "dead"
        return state

    def _combat(self, state: DungeonState, cfg: DungeonConfig) -> None:
        hero = state.hero
        cell = (hero["x"], hero["y"])
        monster = next((m for m in state.monsters if (m["x"], m["y"]) == cell), None)
        if monster is None:
            return
        log = resolve_encounter(self._rng, hero, monster, cfg)
        if monster["hp"] <= 0:
            state.monsters.remove(monster)
            if monster["kind"] == "boss":
                state.status = "won"
                hero["gold"] += 25
            else:
                hero["xp"] += cfg.xp_per_kill
                hero["gold"] += 5
            self._maybe_take_weapon(hero, monster, cfg, log)
        state.combat_log = log[-COMBAT_LOG_LINES:]
        for m in state.monsters:
            m.pop("frozen", None)
        hero.pop("frozen", None)

    def _maybe_take_weapon(self, hero: dict, monster: dict, cfg: DungeonConfig, log: list[str]) -> None:
        current = hero.get("weapon") or {}
        if monster.get("kind") == "boss" and cfg.boss_legendary_drop:
            drop = make_legendary(self._rng)  # bosses always drop a legendary object
        else:
            if self._rng.random() >= cfg.weapon_drop_chance:
                return
            drop = monster.get("weapon") or {}
        if _weapon_score(drop) > _weapon_score(current):
            hero["weapon"] = dict(drop)
            label = "legendary " if drop.get("key") in LEGENDARY_TABLE else ""
            log.append(f"{hero['name']} takes the {label}{drop['name']}!")

    def _loot(self, state: DungeonState, cfg: DungeonConfig) -> None:
        hero = state.hero
        cell = (hero["x"], hero["y"])
        if cell in state.potions:
            state.potions.remove(cell)
            hero["hp"] = min(hero["max_hp"], hero["hp"] + cfg.potion_heal)

    def _level_up(self, state: DungeonState, cfg: DungeonConfig) -> None:
        hero = state.hero
        while hero["xp"] >= cfg.xp_level_up and state.status == "running":
            hero["xp"] -= cfg.xp_level_up
            hero["level"] += 1
            hero["dmg"] += 2
            hero["max_hp"] += 6
            trait = random_trait(self._rng, [t.get("key", t["name"]) for t in hero["traits"]], cfg)
            if trait is not None:
                hero["traits"].append(trait)
                hero["max_hp"] += trait.get("max_hp", 0)
            hero["hp"] = hero["max_hp"]

    def _maybe_spawn(self, state: DungeonState, cfg: DungeonConfig) -> None:
        if self._rng.random() >= cfg.spawn_chance:
            return
        n = state.grid_size
        occupied = {(m["x"], m["y"]) for m in state.monsters}
        occupied.add((state.hero["x"], state.hero["y"]))
        occupied.update(state.potions)
        free = sorted((x, y) for x in range(n) for y in range(n) if (x, y) not in occupied)
        if not free:
            return
        spawned = self._spawner.spawn(free)
        if spawned is None:
            return
        cell, kind = spawned
        if kind == "monster":
            # monsters scale with dungeon depth (turns) and requested difficulty
            level = 1 + min(2, state.turn // 60) + (clamp_difficulty(cfg.difficulty) - 1) // 3
            state.monsters.append(make_monster(self._rng, cell[0], cell[1], cfg, kind="monster", level=level))
        else:
            state.potions.append(cell)
