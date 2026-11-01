/* ViewModel — owns client state. The game loop runs on the server;
   the client polls /api/state and interpolates for smooth rendering. */
window.SnakeViewModel = class SnakeViewModel {
  constructor(api) {
    this.api = api;
    this.state = null;
    this.running = false;
    this.started = false;
    this.torus = true;
    this._last = 0;
    this._acc = 0;
    this._prevSnake = null;
    this._pollTimer = null;
    this.onStateChange = () => {};
    this.onGameOver = () => {};
  }

  async init() {
    const s = await this.api.getState();
    this.torus = s.torus;
    this.state = s;
    this.running = s.status === 'running';
    this.started = this.running;
    this._startPolling();
    this.onStateChange();
  }

  async start() {
    this.state = await this.api.newGame(this.torus);
    this._prevSnake = null;
    this._acc = 0;
    this.running = true;
    this.started = true;
    this._startPolling();
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
    this.onStateChange();
  }

  queueDirection(name) {
    if (!this.running) return;
    this.api.setDirection(name);
  }

  _startPolling() {
    if (this._pollTimer) return;
    const poll = async () => {
      try {
        const s = await this.api.getState();
        if (this.running && s.status !== 'running') {
          this.running = false;
          this._pollTimer = null;
          this.onGameOver();
        }
        this.state = s;
        this.onStateChange();
      } catch (e) { /* keep polling */ }
      this._pollTimer = setTimeout(poll, 80);
    };
    this._pollTimer = setTimeout(poll, 80);
  }

  /* Advance the loop; returns true while running. */
  tick(now) {
    if (!this.running || !this.state) return this.running;
    const dt = Math.min(100, now - this._last);
    this._last = now;
    this._acc += dt;
    return this.running;
  }

  interpolation() {
    if (!this.state) return 1;
    return this.running ? Math.min(1, this._acc / this.state.stepTimeMs) : 1;
  }
};
