/* Composition root / game shell: loads the game picker, then loads the
   selected game's view module from static/games/<id>/ behind the GameView
   interface with an error boundary so one game cannot kill the shell. */
(function () {
  const shell = {
    vm: null,
    view: null,
    game: null,
  };

  async function loadScript(src) {
    return new Promise((resolve, reject) => {
      const el = document.createElement('script');
      el.src = src;
      el.onload = resolve;
      el.onerror = () => reject(new Error('failed to load ' + src));
      document.head.appendChild(el);
    });
  }

  async function loadGameModule(gameId) {
    const base = '/static/games/' + gameId + '/';
    await loadScript(base + 'view.js');
    // optional per-game modules; snake ships scene/hud/input, others may not
    for (const src of ['scene.js', 'hud.js', 'input.js']) {
      await fetch(base + src, { method: 'HEAD' }).then((r) => {
        if (r.ok) return loadScript(base + src);
      });
    }
  }

  function freshCanvas() {
    // a canvas locks to its first context type (2d vs webgl), so each game
    // gets a fresh element instead of the one the previous game used
    const old = document.getElementById('scene');
    const canvas = old.cloneNode(false);
    old.parentNode.replaceChild(canvas, old);
    return canvas;
  }

  async function startGame(game) {
    disposeGame();
    shell.game = game;
    await loadGameModule(game.id);
    const Ctor = window['GameView_' + game.id];
    if (!Ctor) throw new Error('no GameView for game: ' + game.id);
    const vm = new GameViewModel(ApiClient, game);
    const view = new Ctor(freshCanvas());
    shell.vm = vm;
    shell.view = view;

    vm.onStateChange = () => {
      view.updateHud(vm);
      if (vm.running) view.hideOverlay();
    };
    vm.onGameOver = () => {
      view.updateHud(vm);
      const multi = vm.mode === 'multi';
      const msg = multi
        ? 'P1: ' + vm.state.score + ' · P2: ' + ((vm.state.scores && vm.state.scores[1]) || 0) +
          '  ·  Rekord: ' + ((vm.meta && vm.meta.best) || 0)
        : 'Punkte: ' + vm.state.score + '  ·  Rekord: ' + ((vm.meta && vm.meta.best) || 0);
      view.showOverlay('GAME OVER', msg, 'Tippen für Neustart');
    };

    let starting = false;
    async function startIfNeeded() {
      if (starting || vm.running) return;
      starting = true;
      try {
        await vm.start(vm.mode);
      } finally {
        starting = false;
      }
    }

    view.dom.overlay.addEventListener('pointerdown', startIfNeeded);
    view.dom.torusBtn.addEventListener('pointerdown', (e) => { e.stopPropagation(); vm.toggleTorus(); });
    view.dom.modeBtn.addEventListener('pointerdown', (e) => { e.stopPropagation(); vm.toggleMode(); });
    view.dom.speed.addEventListener('input', (e) => vm.setSpeed(parseInt(e.target.value, 10)));

    let input = null;
    if (window.SnakeInput) {
      input = new SnakeInput(vm, view, startIfNeeded);
      shell.input = input;
    } else {
      window.addEventListener('keydown', (e) => {
        const map = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' };
        if (map[e.key]) { e.preventDefault(); vm.running ? vm.queueDirection(map[e.key]) : startIfNeeded(); }
      });
      view.dom.overlay.addEventListener('pointerdown', startIfNeeded);
    }

    function frame(now) {
      requestAnimationFrame(frame);
      try { view.render(vm, now); } catch (e) { /* error boundary: keep shell alive */ }
    }

    try {
      await vm.init();
    } catch (e) {}
    view.updateHud(vm);
    requestAnimationFrame(frame);
  }

  function disposeGame() {
    if (shell.vm) shell.vm._stopTransport();
    if (shell.input && shell.input.dispose) shell.input.dispose();
    if (shell.view && shell.view.dispose) shell.view.dispose();
    shell.vm = null;
    shell.view = null;
    shell.input = null;
  }

  async function init() {
    const games = await ApiClient.listGames();
    const picker = document.getElementById('gamePicker');
    picker.innerHTML = '';
    for (const g of games) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = g.name;
      btn.dataset.gameId = g.id;
      btn.addEventListener('click', () => startGame(g));
      picker.appendChild(btn);
    }
    if (games.length > 0) await startGame(games[0]);
  }

  init();
})();
