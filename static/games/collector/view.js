/* Collector view — minimal GameView implementation for the 2D collector game.
   Implements render(vm, now), updateHud(vm), showOverlay, dispose. */
(function () {
  const COLORS = { bg: '#0b1020', grid: '#1c2740', dot: '#ffe14d', pos: '#4dff88' };

  window.GameView_collector = class CollectorView {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.dom = {
        overlay: document.getElementById('overlay'),
        ovTitle: document.getElementById('ovTitle'),
        ovMsg: document.getElementById('ovMsg'),
        ovCta: document.getElementById('ovCta'),
        torusBtn: document.getElementById('torusBtn'),
        modeBtn: document.getElementById('modeBtn'),
        speed: document.getElementById('speed'),
        score: document.getElementById('score'),
        score2: document.getElementById('score2'),
        best: document.getElementById('best'),
        height: document.getElementById('height'),
        star: document.getElementById('star'),
      };
    }

    showOverlay(title, msg, cta) {
      this.dom.ovTitle.textContent = title;
      this.dom.ovMsg.textContent = msg;
      this.dom.ovCta.textContent = cta;
      this.dom.overlay.classList.remove('hidden');
    }

    hideOverlay() { this.dom.overlay.classList.add('hidden'); }

    updateHud(vm) {
      if (!vm.state) return;
      this.dom.score.textContent = vm.state.score;
      this.dom.best.textContent = vm.state.best || 0;
    }

    render(vm) {
      const s = vm.state;
      if (!s || !s.gridSize) return;
      const c = this.canvas, ctx = this.ctx;
      const n = s.gridSize, size = Math.min(c.width, c.height) || 400;
      const cell = size / n;
      ctx.fillStyle = COLORS.bg;
      ctx.fillRect(0, 0, size, size);
      ctx.strokeStyle = COLORS.grid;
      for (let i = 0; i <= n; i++) {
        ctx.beginPath(); ctx.moveTo(i * cell, 0); ctx.lineTo(i * cell, size); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, i * cell); ctx.lineTo(size, i * cell); ctx.stroke();
      }
      ctx.fillStyle = COLORS.dot;
      for (const d of s.dots || []) {
        ctx.beginPath(); ctx.arc((d[0] + 0.5) * cell, (d[1] + 0.5) * cell, cell * 0.3, 0, 7); ctx.fill();
      }
      ctx.fillStyle = COLORS.pos;
      ctx.fillRect(s.pos[0] * cell + 2, s.pos[1] * cell + 2, cell - 4, cell - 4);
    }

    dispose() {}
  };
})();
