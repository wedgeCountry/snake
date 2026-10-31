/* Composition root: wires ApiClient -> ViewModel -> View, owns input events. */
(function () {
  const vm = new SnakeViewModel(ApiClient);
  const view = new SnakeView(document.getElementById('scene'));

  vm.onStateChange = () => view.updateHud(vm);
  vm.onGameOver = () => {
    view.updateHud(vm);
    view.showOverlay('GAME OVER', 'Punkte: ' + vm.state.score + '  ·  Rekord: ' + (vm.state.best || 0), 'Tippen für Neustart');
  };

  async function startIfNeeded() {
    if (!vm.started || !vm.running) {
      if (!vm.running) await vm.start();
    }
  }

  view.dom.overlay.addEventListener('pointerdown', startIfNeeded);
  view.dom.torusBtn.addEventListener('pointerdown', (e) => { e.stopPropagation(); vm.toggleTorus(); });
  view.dom.speed.addEventListener('input', (e) => vm.setSpeed(parseInt(e.target.value, 10)));

  /* Touch input: 1 finger swipe (rotated 45°), 2-finger pinch = up/down */
  const touches = {};
  let swipeStart = null, pinchDist = 0, pinched = false;
  window.addEventListener('touchstart', (e) => {
    for (const t of e.changedTouches) touches[t.identifier] = { x: t.clientX, y: t.clientY };
    const ids = Object.keys(touches);
    if (ids.length === 1) { swipeStart = { ...touches[ids[0]] }; pinched = false; }
    if (ids.length === 2) {
      const a = touches[ids[0]], b = touches[ids[1]];
      pinchDist = Math.hypot(a.x - b.x, a.y - b.y);
    }
  }, { passive: true });
  window.addEventListener('touchmove', (e) => {
    e.preventDefault();
    for (const t of e.changedTouches) if (touches[t.identifier]) touches[t.identifier] = { x: t.clientX, y: t.clientY };
    const ids = Object.keys(touches);
    if (ids.length === 2 && vm.running) {
      const a = touches[ids[0]], b = touches[ids[1]];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const delta = d - pinchDist;
      if (Math.abs(delta) >= 28) {
        vm.queueDirection(delta > 0 ? 'down' : 'up');
        pinchDist = d;
        pinched = true;
      }
    }
  }, { passive: false });
  window.addEventListener('touchend', (e) => {
    const t = e.changedTouches[0];
    const ended = { x: t.clientX, y: t.clientY };
    for (const tt of e.changedTouches) delete touches[tt.identifier];
    const ids = Object.keys(touches);
    if (ids.length === 0 && swipeStart && vm.running && !pinched) {
      const dx = ended.x - swipeStart.x, dy = ended.y - swipeStart.y;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) { startIfNeeded(); }
      else {
        const wx = dx + dy, wz = dy - dx;
        if (Math.abs(wx) > Math.abs(wz)) vm.queueDirection(wx > 0 ? 'right' : 'left');
        else vm.queueDirection(wz > 0 ? 'forward' : 'back');
      }
    }
    if (ids.length < 2) pinchDist = 0;
    if (ids.length === 0) { swipeStart = null; pinched = false; }
  }, { passive: true });

  window.addEventListener('keydown', (e) => {
    const map = {
      ArrowUp: 'back', ArrowDown: 'forward', ArrowLeft: 'left', ArrowRight: 'right',
      PageUp: 'up', '+': 'up', '=': 'up', PageDown: 'down', '-': 'down',
    };
    if (map[e.key]) { e.preventDefault(); vm.queueDirection(map[e.key]); }
  });
  window.addEventListener('wheel', (e) => {
    if (!vm.running) return;
    e.preventDefault();
    vm.queueDirection(e.deltaY < 0 ? 'down' : 'up');
  }, { passive: false });
  window.addEventListener('contextmenu', (e) => e.preventDefault());

  function frame(now) {
    requestAnimationFrame(frame);
    vm.tick(now);
    view.render(vm, now);
  }

  vm.init().then(() => { view.updateHud(vm); requestAnimationFrame(frame); });
})();
