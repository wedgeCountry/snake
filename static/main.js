/* Composition root / game shell: loads the game picker, then loads the
   selected game's view module from static/games/<id>/ behind the GameView
   interface with an error boundary so one game cannot kill the shell. */
(function () {
  const shell = {
    vm: null,
    view: null,
    game: null,
    overlayTap: null,
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
    // shared building blocks first (2D grid view base), then the game's own view
    await loadScript('/static/games/common/grid2d.js');
    await loadScript(base + 'view.js');
    // optional per-game modules; snake ships scene/hud/input, others may not.
    // They only reference each other at construction time, so they can load
    // in parallel once view.js is in.
    await Promise.all(['scene.js', 'hud.js', 'input.js'].map(async (src) => {
      const r = await fetch(base + src, { method: 'HEAD' });
      if (r.ok) await loadScript(base + src);
    }));
  }

  function freshCanvas() {
    // a canvas locks to its first context type (2d vs webgl), so each game
    // gets a fresh element instead of the one the previous game used
    const old = document.getElementById('scene');
    const canvas = old.cloneNode(false);
    // drop any inline size a previous 3D renderer wrote; each view sizes itself
    canvas.removeAttribute('style');
    old.parentNode.replaceChild(canvas, old);
    return canvas;
  }

  function showGameSelect(errorMsg) {
    document.body.classList.add('no-game');
    document.getElementById('overlay').classList.add('hidden');
    const err = document.getElementById('gameSelectError');
    err.textContent = errorMsg || '';
    err.style.display = errorMsg ? '' : 'none';
  }

  async function startGame(game) {
    disposeGame();
    shell.game = game;
    try {
      await startGameInner(game);
    } catch (e) {
      // error boundary: a broken game module must not kill the shell
      showGameSelect('Spiel "' + game.name + '" konnte nicht geladen werden: ' + e.message);
    }
  }

  async function startGameInner(game) {
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
    shell.overlayTap = startIfNeeded;
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
        if (map[e.key]) { e.preventDefault(); vm.running ? vm.queueDirection(map[e.key]) : startIfNeeded(); return; }
        if (e.key === 'e' && vm.running) vm.enchant(''); // enchant weapon (default school)
        if (e.key === 's' && vm.running) vm.saveGame('').catch(() => {}); // savegame
        if (e.key === 'l') vm.listSavegames().then((l) => { if (l.length) vm.loadGame(l[0].id).catch(() => {}); }).catch(() => {}); // load latest
      });
    }

    function frame(now) {
      requestAnimationFrame(frame);
      try { view.render(vm, now); } catch (e) { /* error boundary: keep shell alive */ }
    }

    try {
      await vm.init();
    } catch (e) {}
    view.updateHud(vm);
    document.body.classList.remove('no-game');
    // no running session yet: show the game's start screen
    if (!vm.running) view.showOverlay(game.name, 'Bereit zum Spielen?', 'Tippen zum Starten');
    requestAnimationFrame(frame);
  }

  function disposeGame() {
    if (shell.overlayTap) {
      document.getElementById('overlay').removeEventListener('pointerdown', shell.overlayTap);
      shell.overlayTap = null;
    }
    if (shell.vm) shell.vm._stopTransport();
    if (shell.input && shell.input.dispose) shell.input.dispose();
    if (shell.view && shell.view.dispose) shell.view.dispose();
    shell.vm = null;
    shell.view = null;
    shell.input = null;
  }

  function gameMeta(g) {
    return (g.maxPlayers > 1 ? '1\u2013' + g.maxPlayers + ' Spieler' : '1 Spieler') +
      (g.realTime ? ' \u00b7 Echtzeit' : '');
  }

  async function init() {
    const games = await ApiClient.listGames();
    const list = document.getElementById('gameSelectList');
    list.innerHTML = '';
    for (const g of games) {
      // the game-select menu is the only way to pick a game; there is no
      // in-game switching
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'game-select-card';
      card.dataset.gameId = g.id;
      const label = document.createElement('span');
      label.textContent = g.name;
      const meta = document.createElement('span');
      meta.className = 'meta';
      meta.textContent = gameMeta(g);
      card.appendChild(label);
      card.appendChild(meta);
      card.addEventListener('click', () => startGame(g));
      list.appendChild(card);
    }
    // first step is always "select a game"; no game is auto-started
    showGameSelect();
  }

  window.__shell = shell; // test hook: lets GUI tests inspect the active viewmodel
  init();
})();
