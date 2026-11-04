/* Dungeon input — the dungeon game's own controls (not the snake gestures):
   arrow keys or WASD steer the party on the 2D grid, E enchants the leader's
   weapon; any steering key also starts the game from the start screen. */
window.DungeonInput = class DungeonInput {
  constructor(vm, view, onStart) {
    this.vm = vm;
    this.onStart = onStart;
    this._handlers = [];
    this._onKey = (e) => {
      if (e.repeat) return; // one press = one tile: ignore key auto-repeat
      const steer = {
        ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right',
        w: 'up', s: 'down', a: 'left', d: 'right',
      };
      const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      if (steer[k]) {
        e.preventDefault();
        if (this.vm.running) this.vm.queueDirection(steer[k]);
        else this.onStart();
        return;
      }
      if (k === 'e' && this.vm.running) {
        e.preventDefault();
        this.vm.enchant('');
      }
    };
    window.addEventListener('keydown', this._onKey);
    this._handlers.push(['keydown', this._onKey]);
  }

  dispose() {
    for (const [ev, fn] of this._handlers) window.removeEventListener(ev, fn);
    this._handlers = [];
  }
};
