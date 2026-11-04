/* JS-side contract tests for the GameView interface and the viewmodel's
   envelope handling. Run with: node static/tests/run.js */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

let failures = 0;
function assert(cond, msg) {
  if (!cond) { failures++; console.error('FAIL: ' + msg); }
  else console.log('ok: ' + msg);
}

function loadViewModel() {
  const sandbox = {
    window: {},
    location: { protocol: 'http:', host: 'x' },
    setTimeout: () => 0,
    clearTimeout: () => {},
  };
  vm.createContext(sandbox);
  const src = fs.readFileSync(path.join(__dirname, '..', 'viewmodel.js'), 'utf8');
  vm.runInContext(src, sandbox);
  return sandbox.window.GameViewModel;
}

function fakeApi(envelopes) {
  let i = 0;
  return {
    listGames: async () => [{ id: 'snake', name: '3D Snake', realTime: true, maxPlayers: 2 }],
    newGame: async (gameId, torus, mode) => envelopes.new || envelopes.state,
    getState: async () => envelopes.state,
    sendAction: async () => ({ ok: true }),
    getLeaderboard: async () => ({ top: [] }),
    setSettings: async () => ({}),
    poll: async () => envelopes.poll ? envelopes.poll[i++ % envelopes.poll.length] : envelopes.state,
    subscribe: () => ({ close() {} }),
  };
}

function env(status, score) {
  return { v: 1, gameId: 'snake', sessionId: 's1', status, players: ['u1'],
           state: { score, status, snake: [{ x: 3, y: 5, z: 6 }] }, meta: {} };
}

(async () => {
  const VM = loadViewModel();

  // GameView interface contract (static shape of the snake view)
  const viewSrc = fs.readFileSync(path.join(__dirname, '..', 'games', 'snake', 'view.js'), 'utf8');
  for (const m of ['render(', 'onInput', 'dispose']) {
    if (m === 'onInput') continue; // input module owns gestures
  }
  assert(viewSrc.includes('render(vm, now)'), 'snake view implements render(envelope-bearing vm, now)');
  assert(viewSrc.includes('showOverlay('), 'snake view implements showOverlay');
  assert(viewSrc.includes('updateHud(vm)'), 'snake view implements updateHud');
  assert(viewSrc.includes('dispose()'), 'snake view implements dispose (GameView contract)');
  const inputSrc = fs.readFileSync(path.join(__dirname, '..', 'games', 'snake', 'input.js'), 'utf8');
  assert(inputSrc.includes('dispose()'), 'snake input implements dispose (listener cleanup)');
  for (const key of ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown']) {
    assert(inputSrc.includes(key), 'snake input maps desktop key ' + key);
  }
  assert(/if \(vm\.running\) vm\.queueDirection\(map\[e\.key\]\);\s*else this\.onStart\(\)/.test(inputSrc),
    'snake input starts the game on arrow/PageUp/PageDown when idle (desktop)');

  // Shell: start overlay must not brick the app (first load has no session -> state 404)
  const mainSrc = fs.readFileSync(path.join(__dirname, '..', 'main.js'), 'utf8');
  assert(/try\s*\{\s*await vm\.init\(\);\s*\}\s*catch/.test(mainSrc),
    'shell survives initial state fetch failure (no session cookie yet)');
  assert(mainSrc.includes('if (vm.running) view.hideOverlay();'),
    'shell hides the "Tippen zum Starten" overlay once the game runs');
  assert(/let starting = false;[\s\S]*if \(starting \|\| vm\.running\) return;/.test(mainSrc),
    'startIfNeeded is re-entrancy guarded (pointerdown + touchend double fire)');
  assert(!mainSrc.includes('startGame(games[0])'),
    'shell does not auto-start a game; the first step is the game-select menu');
  assert(!mainSrc.includes("getElementById('gamePicker')"),
    'no in-game game picker: switching games is only possible on the select screen');
  assert(mainSrc.includes('showGameSelect()'),
    'shell shows the game-select menu before any game is chosen');
  assert(mainSrc.includes("/static/games/common/grid2d.js"),
    'shell loads the shared 2D grid view base before each game view');
  const grid2dSrc = fs.readFileSync(path.join(__dirname, '..', 'games', 'common', 'grid2d.js'), 'utf8');
  assert(grid2dSrc.includes('window.Grid2DView'), 'shared Grid2DView base exists');
  assert(/resize\(\)\s*\{[\s\S]*?canvas\.width\s*=/.test(grid2dSrc),
    'Grid2DView.resize sizes the drawing buffer to the viewport (full-screen 2D view)');
  assert(grid2dSrc.includes("addEventListener('resize'") && grid2dSrc.includes("removeEventListener('resize'"),
    'Grid2DView tracks window resize and removes the listener on dispose');
  assert(/this\.dom\.speed\.value\s*=/.test(grid2dSrc),
    'Grid2DView syncs the shared speed slider from meta/state in updateHud');
  const cssSrc = fs.readFileSync(path.join(__dirname, '..', 'style.css'), 'utf8');
  assert(/#scene\s*\{[^}]*width:\s*100%[^}]*height:\s*100%/.test(cssSrc),
    'the #scene canvas fills the viewport instead of the intrinsic 300x150');
  for (const g of ['collector', 'territory', 'dungeon']) {
    const src = fs.readFileSync(path.join(__dirname, '..', 'games', g, 'view.js'), 'utf8');
    assert(src.includes('extends window.Grid2DView'), g + ' view extends the shared Grid2DView');
    assert(src.includes('drawEntities('), g + ' view implements drawEntities');
  }
  assert(mainSrc.includes('window.__shell = shell'),
    'shell is exposed on window.__shell for GUI tests');

  // ViewModel consumes the versioned envelope and dispatches on gameId
  const game = { id: 'snake', name: '3D Snake', realTime: false, maxPlayers: 2 };
  const v = new VM(fakeApi({ state: env('running', 0) }), game);
  await v.init();
  assert(v.envelope.v === 1, 'envelope version read');
  assert(v.gameId === 'snake', 'dispatch key gameId');
  assert(v.running === true && v.state.score === 0, 'state extracted from envelope');
  v._apply({ ...env('running', 0), meta: { best: 42, userId: 'u1' } });
  assert(v.meta.best === 42, 'meta extracted from envelope');
  v._stopTransport();

  // Game over transition fires onGameOver exactly once
  const game2 = { id: 'snake', name: '3D Snake', realTime: false, maxPlayers: 2 };
  const v2 = new VM(fakeApi({ state: env('running', 10), poll: [env('dead', 10)] }), game2);
  let over = 0;
  v2.onGameOver = () => over++;
  await v2.init();
  v2._onEnvelope(env('dead', 10));
  v2._onEnvelope(env('dead', 10));
  assert(over === 1, 'onGameOver fires once on terminal transition');
  v2._stopTransport();

  // Real-time games use subscribe, others poll
  const gameRT = { id: 'snake', name: '3D Snake', realTime: true, maxPlayers: 2 };
  let subscribed = false;
  const apiRT = fakeApi({ state: env('running', 0) });
  apiRT.subscribe = () => { subscribed = true; return { close() {} }; };
  const v3 = new VM(apiRT, gameRT);
  await v3.init();
  assert(subscribed, 'realTime game subscribes via transport');
  v3._stopTransport();

  // A dead WebSocket while the game runs falls back to REST polling
  const gameRT2 = { id: 'snake', name: '3D Snake', realTime: true, maxPlayers: 2 };
  const apiRT2 = fakeApi({ state: env('running', 0), poll: [env('running', 1)] });
  let fakeWs;
  apiRT2.subscribe = () => { fakeWs = { close() {} }; return fakeWs; };
  const v4 = new VM(apiRT2, gameRT2);
  await v4.init();
  fakeWs.onclose();
  assert(v4._timer !== null && v4._timer !== undefined, 'ws close while running falls back to REST polling');
  v4._stopTransport();

  // Dungeon ships its own input module (not the snake gestures): arrows/WASD
  // map to 2D grid directions, E enchants, dispose removes the listener
  assert(/charAt\(0\)\.toUpperCase\(\)[\s\S]*?\+ 'Input'/.test(mainSrc),
    'shell picks the per-game input module (DungeonInput for dungeon) instead of a stale SnakeInput');
  const dungeonInputSrc = fs.readFileSync(path.join(__dirname, '..', 'games', 'dungeon', 'input.js'), 'utf8');
  assert(dungeonInputSrc.includes('window.DungeonInput'), 'dungeon ships its own input module (window.DungeonInput)');
  const inListeners = {};
  const inSandbox = {
    window: {
      addEventListener: (ev, fn) => { inListeners[ev] = fn; },
      removeEventListener: (ev) => { delete inListeners[ev]; },
    },
  };
  vm.createContext(inSandbox);
  vm.runInContext(dungeonInputSrc, inSandbox);
  const queued = [];
  let started = 0;
  const fakeVmD = { running: true, queueDirection: (d) => queued.push(d), enchant: (s) => queued.push('enchant:' + s) };
  const dungeonInput = new inSandbox.window.DungeonInput(fakeVmD, {}, () => started++);
  const key = (k) => inListeners['keydown']({ key: k, preventDefault() {} });
  for (const k of ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'w', 'a', 's', 'd']) key(k);
  key('e');
  assert(JSON.stringify(queued) === JSON.stringify(
    ['up', 'down', 'left', 'right', 'up', 'left', 'down', 'right', 'enchant:']),
    'dungeon input maps arrow keys + WASD to 2D directions and E to enchant');
  const beforeRepeat = queued.length;
  inListeners['keydown']({ key: 'ArrowLeft', repeat: true, preventDefault() {} });
  assert(queued.length === beforeRepeat, 'dungeon input ignores key auto-repeat (one press = one tile)');
  fakeVmD.running = false;
  key('ArrowUp');
  assert(started === 1 && queued.length === 9, 'a steering key on the start screen starts the game');
  dungeonInput.dispose();
  assert(!inListeners['keydown'], 'dungeon input dispose removes the keydown listener');

  // Dungeon view: own canvas rendering + stats button/panel + tap-to-inspect
  const dungeonViewSrc = fs.readFileSync(path.join(__dirname, '..', 'games', 'dungeon', 'view.js'), 'utf8');
  assert(dungeonViewSrc.includes('floorA') && dungeonViewSrc.includes('strokeRect'),
    'dungeon view renders its own checkerboard dungeon floor with border (not the shared plain grid)');
  assert(dungeonViewSrc.includes("'pointerdown'"), 'dungeon view listens for taps on the canvas');
  assert(dungeonViewSrc.includes('dungeon-stats-btn') && dungeonViewSrc.includes('dungeon-panel'),
    'dungeon view creates a stats button + details panel');
  assert(dungeonViewSrc.includes('_showMonster') && dungeonViewSrc.includes('_showParty'),
    'tapping an enemy or the party shows its stats');
  assert(dungeonViewSrc.includes('Lv') && dungeonViewSrc.includes('HP'),
    'canvas stats bar shows level and health per member');

  // functional: instantiate the dungeon view with stub DOM/canvas and exercise it
  function stubEl(tag) {
    return {
      tag, children: [], style: {}, textContent: '', innerHTML: '', className: '', removed: false,
      classList: { _s: new Set(), add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); }, contains(c) { return this._s.has(c); } },
      listeners: {},
      addEventListener(ev, fn) { this.listeners[ev] = fn; },
      removeEventListener(ev) { delete this.listeners[ev]; },
      appendChild(c) { this.children.push(c); },
      remove() { this.removed = true; },
      getBoundingClientRect() { return { left: 0, top: 0, width: 400, height: 400 }; },
    };
  }
  const createdEls = [];
  const canvasStub = Object.assign(stubEl('canvas'), {
    clientWidth: 400, clientHeight: 400, width: 400, height: 400,
    getContext: () => new Proxy({}, { get: (t, k) => (k in t ? t[k] : () => {}), set: () => true }),
  });
  const sandboxV = {
    window: { addEventListener() {}, removeEventListener() {}, devicePixelRatio: 1 },
    document: {
      getElementById: () => stubEl('div'),
      createElement: (tag) => { const el = stubEl(tag); createdEls.push(el); return el; },
      body: { appendChild() {} },
    },
  };
  vm.createContext(sandboxV);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'games', 'common', 'grid2d.js'), 'utf8'), sandboxV);
  vm.runInContext(dungeonViewSrc, sandboxV);
  const DV = sandboxV.window.GameView_dungeon;
  const dv = new DV(canvasStub);
  dv._n = 8; // 400x400 canvas, 8x8 grid -> 50px cells
  assert(JSON.stringify(dv._cellAt(250, 50)) === JSON.stringify([5, 1]), 'tap maps to grid cell [5,1]');
  assert(dv._cellAt(-5, 10) === null, 'tap outside the board maps to null');
  const mState = {
    gridSize: 8,
    party: [{ name: 'Warrior', class: 'warrior', x: 0, y: 0, hp: 36, max_hp: 36, ac: 16, attack: 5,
              level: 1, xp: 0, xpNeeded: 30, weapon: { name: 'Iron Sword', die: 8, bonus: 3 }, traits: [], skills: [] }],
    monsters: [{ name: 'Boss', kind: 'boss', x: 5, y: 1, hp: 46, max_hp: 46, ac: 17, attack: 10,
                 level: 5, weapon: { name: 'Doom Axe', die: 12, bonus: 5 }, traits: [], skills: [] }],
    potions: [], walls: [], combatLog: [],
  };
  let renderThrew = null;
  try { dv.render({ state: mState }); } catch (e) { renderThrew = e; }
  assert(renderThrew === null, 'dungeon render() draws a full state without throwing');
  dv._state = mState;
  const panel = createdEls.find((el) => el.className.includes('dungeon-panel'));
  const btn = createdEls.find((el) => el.className.includes('dungeon-stats-btn'));
  dv._handleTap({ clientX: 250, clientY: 50 });
  assert(panel && !panel.classList.contains('hidden') && panel.innerHTML.includes('Boss') &&
    panel.innerHTML.includes('Doom Axe') && panel.innerHTML.includes('46/46'),
    'tapping the boss cell shows its stats (name, weapon, HP)');
  dv._handleTap({ clientX: 10, clientY: 10 });
  assert(panel.innerHTML.includes('Warrior') && panel.innerHTML.includes('36/36') && panel.innerHTML.includes('Level'),
    'tapping the party cell shows party stats with level and HP');
  dv._handleTap({ clientX: 200, clientY: 200 });
  assert(panel.classList.contains('hidden'), 'tapping an empty cell hides the panel');
  btn.listeners.click({ stopPropagation() {} });
  assert(!panel.classList.contains('hidden') && panel.innerHTML.includes('Gruppe'),
    'stats button opens the party details panel');
  btn.listeners.click({ stopPropagation() {} });
  assert(panel.classList.contains('hidden'), 'stats button toggles the panel closed');
  dv.dispose();
  assert(canvasStub.listeners['pointerdown'] === undefined && btn.removed && panel.removed,
    'dispose removes the tap listener, stats button and panel');

  if (failures) { console.error(failures + ' contract test(s) failed'); process.exit(1); }
  console.log('All JS contract tests passed');
})();
