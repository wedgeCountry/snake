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

  if (failures) { console.error(failures + ' contract test(s) failed'); process.exit(1); }
  console.log('All JS contract tests passed');
})();
