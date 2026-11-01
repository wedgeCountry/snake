/* ViewModel — owns client state. The game loop runs on the server;
   the client polls /api/state. */
window.SnakeViewModel = class SnakeViewModel {
  constructor(api) {
    this.api = api;
    this.state = null;
    this.running = false;
    this.started = false;
    this.torus = true;
    this.mode = 'single';
    this.leaderboard = [];
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

  async start(mode) {
    this.mode = mode || 'single';
    this.state = await this.api.newGame(this.torus, this.mode);
    this.running = true;
    this.started = true;
    this._startPolling();
    this.onStateChange();
  }

  async loadLeaderboard() {
    const lb = await this.api.getLeaderboard(this.mode);
    this.leaderboard = lb.top || [];
    return this.leaderboard;
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
};
