/* Composition root: wires ApiClient -> ViewModel -> View + Input. */
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

  new SnakeInput(vm, view, startIfNeeded);

  function frame(now) {
    requestAnimationFrame(frame);
    view.render(vm, now);
  }

  vm.init().then(() => { view.updateHud(vm); requestAnimationFrame(frame); });
})();
