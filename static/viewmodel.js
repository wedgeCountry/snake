/* ViewModel — owns client state for the active game. Consumes the versioned
   envelope {v, gameId, sessionId, status, players, state, meta} and dispatches
   on gameId. Transport: subscribes when the game is realTime, else polls. */
window.GameViewModel = class GameViewModel {
  constructor(api, game) {
    this.api = api;
    this.game = game; // {id, name, realTime, maxPlayers}
    this.state = null;
    this.envelope = null;
    this.running = false;
    this.started = false;
    this.torus = true;
    this.mode = 'single';
    this.leaderboard = [];
    this._timer = null;
    this._ws = null;
    this.onStateChange = () => {};
    this.onGameOver = () => {};
  }

  get gameId() { return this.game.id; }

  async init() {
    const env = await this.api.getState(this.gameId);
    this._apply(env);
    this._startTransport();
    this.onStateChange();
  }

  async start(mode) {
    this.mode = mode || 'single';
    const env = await this.api.newGame(this.gameId, this.torus, this.mode);
    this._stopTransport();
    this._apply(env);
    this.running = true;
    this.started = true;
    this._startTransport();
    this.onStateChange();
  }

  async loadLeaderboard() {
    const lb = await this.api.getLeaderboard(this.gameId, this.mode);
    this.leaderboard = lb.top || [];
    return this.leaderboard;
  }

  async toggleTorus() {
    this.torus = !this.torus;
    await this.api.setSettings({ torus: this.torus });
    if (this.started && this.running) await this.api.newGame(this.gameId, this.torus, this.mode);
    this.onStateChange();
  }

  async setSpeed(ms) {
    await this.api.setSettings({ step_time_ms: ms });
    this.onStateChange();
  }

  queueDirection(name, player) {
    if (!this.running) return;
    this.api.sendAction(this.gameId, player || 0, { direction: name });
  }

  async toggleMode() {
    this.mode = this.mode === 'single' ? 'multi' : 'single';
    await this.start(this.mode);
  }

  _apply(env) {
    this.envelope = env;
    this.state = env.state;
    this.running = env.status === 'running';
    if (!this.started) this.started = this.running;
  }

  _onEnvelope(env) {
    const wasRunning = this.running;
    this._apply(env);
    if (wasRunning && env.status !== 'running') {
      this.running = false;
      this._stopTransport();
      this.onGameOver();
    }
    this.onStateChange();
  }

  _startTransport() {
    if (this.game.realTime && this.envelope && this.envelope.sessionId) {
      this._ws = this.api.subscribe(this.gameId, this.envelope.sessionId,
        (env) => this._onEnvelope(env));
    } else {
      this._startPolling();
    }
  }

  _stopTransport() {
    if (this._ws) { try { this._ws.close(); } catch (e) {} this._ws = null; }
    if (this._timer) { clearTimeout(this._timer); this._timer = null; }
  }

  _startPolling() {
    if (this._timer) return;
    const poll = async () => {
      try {
        this._onEnvelope(await this.api.poll(this.gameId));
      } catch (e) { /* keep polling */ }
      this._timer = setTimeout(poll, 80);
    };
    this._timer = setTimeout(poll, 80);
  }
};
