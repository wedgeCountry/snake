/* ViewModel — owns game state, game loop and input mapping.
   The View only renders what the ViewModel exposes. */
window.SnakeViewModel = class SnakeViewModel {
  constructor(api) {
    this.api = api;
    this.state = null;
    this.running = false;
    this.started = false;
    this.torus = true;
    this._dirQueue = [];
    this._acc = 0;
    this._last = 0;
    this.onStateChange = () => {};
    this.onGameOver = () => {};
  }

  async init() {
    const s = await this.api.getState();
    this.torus = s.torus;
    this.state = s;
    this.onStateChange();
  }

  async start() {
    this.state = await this.api.newGame(this.torus);
    this._dirQueue = [];
    this.running = true;
    this.started = true;
    this.onStateChange();
  }

  async toggleTorus() {
    this.torus = !this.torus;
    await this.api.setSettings({ torus: this.torus });
    if (this.started && this.running) await this.api.newGame(this.torus);
    this.onStateChange();
  }

  async setSpeed(ms) {
    await this.api.setSettings({ step_time_ms: ms });
    if (this.state) this.state.stepTimeMs = ms;
    this.onStateChange();
  }

  queueDirection(name) {
    if (!this.running) return;
    const map = { left: [-1, 0, 0], right: [1, 0, 0], up: [0, 1, 0], down: [0, -1, 0], forward: [0, 0, 1], back: [0, 0, -1] };
    const [x, y, z] = map[name];
    const last = this._dirQueue.length ? this._dirQueue[this._dirQueue.length - 1] : this.state.direction;
    if ((x === last.x && y === last.y && z === last.z) || (x === -last.x && y === -last.y && z === -last.z)) return;
    if (this._dirQueue.length < 4) {
      this._dirQueue.push({ x, y, z });
      this.api.setDirection(name).then((s) => { this.state = s; });
    }
  }

  /* Advance the loop; returns true while running. */
  async tick(now) {
    if (!this.running) return false;
    const dt = Math.min(100, now - this._last);
    this._last = now;
    this._acc += dt;
    const stepMs = this.state.stepTimeMs;
    while (this._acc >= stepMs && this.running) {
      this._acc -= stepMs;
      const s = await this.api.step();
      this.state = s;
      if (s.status !== 'running') {
        this.running = false;
        const r = await this.api.gameOver();
        this.state.best = r.best;
        this.onGameOver();
      }
    }
    this.onStateChange();
    return this.running;
  }

  interpolation() {
    if (!this.state) return 1;
    return this.running ? Math.min(1, this._acc / this.state.stepTimeMs) : 1;
  }
};
