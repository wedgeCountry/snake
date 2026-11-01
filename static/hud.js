/* Hud — DOM overlay/score/speed controls, kept separate from rendering. */
window.SnakeHud = class SnakeHud {
  constructor() {
    this.dom = {
      score: document.getElementById('score'),
      score2: document.getElementById('score2'),
      best: document.getElementById('best'),
      height: document.getElementById('height'),
      torusBtn: document.getElementById('torusBtn'),
      modeBtn: document.getElementById('modeBtn'),
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
    const multi = vm.mode === 'multi' && s.mode === 'multi';
    this.dom.score.textContent = s.score;
    if (this.dom.score2) {
      this.dom.score2.parentElement.style.display = multi ? '' : 'none';
      if (multi) this.dom.score2.textContent = (s.scores && s.scores[1]) || 0;
    }
    this.dom.best.textContent = s.best || 0;
    this.dom.height.textContent = s.snake[0].y;
    this.dom.torusBtn.textContent = 'Torus: ' + (vm.torus ? 'An' : 'Aus');
    if (this.dom.modeBtn) this.dom.modeBtn.textContent = multi ? 'Modus: Multi' : 'Modus: Single';
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
