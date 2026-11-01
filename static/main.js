/* Composition root: wires ApiClient -> ViewModel -> View + Input. */
(function () {
  const vm = new SnakeViewModel(ApiClient);
  const view = new SnakeView(document.getElementById('scene'));

  vm.onStateChange = () => view.updateHud(vm);
  vm.onGameOver = () => {
    view.updateHud(vm);
    const multi = vm.mode === 'multi';
    const msg = multi
      ? 'P1: ' + vm.state.score + ' · P2: ' + ((vm.state.scores && vm.state.scores[1]) || 0) +
        '  ·  Rekord: ' + (vm.state.best || 0)
      : 'Punkte: ' + vm.state.score + '  ·  Rekord: ' + (vm.state.best || 0);
    view.showOverlay('GAME OVER', msg, 'Tippen für Neustart');
  };

  async function startIfNeeded() {
    if (!vm.started || !vm.running) {
      if (!vm.running) await vm.start(vm.mode);
    }
  }

  view.dom.overlay.addEventListener('pointerdown', startIfNeeded);
  view.dom.torusBtn.addEventListener('pointerdown', (e) => { e.stopPropagation(); vm.toggleTorus(); });
  view.dom.modeBtn.addEventListener('pointerdown', (e) => { e.stopPropagation(); vm.toggleMode(); });
  view.dom.speed.addEventListener('input', (e) => vm.setSpeed(parseInt(e.target.value, 10)));

  new SnakeInput(vm, view, startIfNeeded);

  function frame(now) {
    requestAnimationFrame(frame);
    view.render(vm, now);
  }

  vm.init().then(() => { view.updateHud(vm); requestAnimationFrame(frame); });
})();
