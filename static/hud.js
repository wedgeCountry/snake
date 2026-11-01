/* Hud — DOM overlay/score/speed controls, kept separate from rendering. */
window.SnakeHud = class SnakeHud {
  constructor() {
    this.dom = {
      score: document.getElementById('score'),
      best: document.getElementById('best'),
      height: document.getElementById('height'),
      torusBtn: document.getElementById('torusBtn'),
      speed: document.getElementById('speed'),
      overlay: document.getElementById('overlay'),
      ovTitle: document.getElementById('ovTitle'),
      ovMsg: document.getElementById('ovMsg'),
      ovCta: document.getElementById('ovCta'),
    };
  }

  update(vm) {
    const s = vm.state;
    if (!s) return;
    this.dom.score.textContent = s.score;
    this.dom.best.textContent = s.best || 0;
    this.dom.height.textContent = s.snake[0].y;
    this.dom.torusBtn.textContent = 'Torus: ' + (vm.torus ? 'An' : 'Aus');
    if (document.activeElement !== this.dom.speed) this.dom.speed.value = s.stepTimeMs;
  }

  showOverlay(title, msg, cta) {
    this.dom.ovTitle.textContent = title;
    this.dom.ovMsg.textContent = msg;
    this.dom.ovCta.textContent = cta;
    this.dom.overlay.classList.remove('hidden');
  }

  hideOverlay() { this.dom.overlay.classList.add('hidden'); }
};
