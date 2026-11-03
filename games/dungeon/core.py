"""Dungeon core — a pure single-player RPG: guide a hero through a grid
dungeon, fight monsters, grab potions, level up, and slay the boss in the far
corner. Zero I/O, injectable RNG. Implements the pipeline Game protocol."""

from __future__ import annotations

import random
from typing import Any

from ..common.direction import Direction, DirectionQueue
from ..common.grid_move import clamp2d
from ..common.spawner import WeightedSpawner
from ..engine import GameState
from .config import DungeonConfig


class DungeonState(GameState):
    state_schema_version = 1

    def __init__(self, grid_size: int, hero: dict, monsters: list[dict],
                 potions: list[tuple[int, int]], score: int, turn: int, max_turns: int,
                 status: str = "running", step_time_ms: int = 300) -> None:
        self.grid_size = grid_size
        self.hero = hero  # {x, y, hp, max_hp, dmg, level, xp, gold}
        self.monsters = monsters  # [{x, y, hp, kind}]
        self.potions = list(potions)
        self.score = score
        self.turn = turn
        self.max_turns = max_turns
        self.status = status
        self.step_time_ms = step_time_ms


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
        hero = {"x": 0, "y": 0, "hp": cfg.hero_hp, "max_hp": cfg.hero_hp,
                "dmg": cfg.hero_dmg, "level": 1, "xp": 0, "gold": 0}
        boss = {"x": n - 1, "y": n - 1, "hp": cfg.boss_hp, "kind": "boss"}
        self._state = DungeonState(n, hero, [boss], [], 0, 0, cfg.max_turns,
                                   step_time_ms=cfg.step_time_ms)
        self._config = cfg
        self._queue.clear()
        self._last = Direction(1, 0, 0)
        return self._state

    def state(self) -> DungeonState:
        if self._state is None:
            return self.init()
        return self._state

    def max_players(self) -> int:
        return 1

    def is_terminal(self) -> bool:
        return self.state().status != "running"

    def apply_action(self, player: int, action: dict[str, Any]) -> None:
        if player != 0:
            raise ValueError("dungeon is single-player")
        direction = Direction.from_name_2d(str(action["direction"]))
        self._queue.push(direction, self._last)

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
        while hero["xp"] >= cfg.xp_level_up and state.status == "running":
            hero["xp"] -= cfg.xp_level_up
            hero["level"] += 1
            hero["dmg"] += 2
            hero["max_hp"] += 6
            hero["hp"] = hero["max_hp"]
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
        monster["hp"] -= hero["dmg"]
        if monster["hp"] <= 0:
            state.monsters.remove(monster)
            if monster["kind"] == "boss":
                state.status = "won"
                hero["gold"] += 25
            else:
                hero["xp"] += cfg.xp_per_kill
                hero["gold"] += 5
        else:
            hero["hp"] -= cfg.boss_dmg if monster["kind"] == "boss" else cfg.monster_dmg

    def _loot(self, state: DungeonState, cfg: DungeonConfig) -> None:
        hero = state.hero
        cell = (hero["x"], hero["y"])
        if cell in state.potions:
            state.potions.remove(cell)
            hero["hp"] = min(hero["max_hp"], hero["hp"] + cfg.potion_heal)

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
            state.monsters.append({"x": cell[0], "y": cell[1], "hp": cfg.monster_hp, "kind": "monster"})
        else:
            state.potions.append(cell)
