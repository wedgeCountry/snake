/* Shared 2D grid view base for grid games (collector, territory, dungeon).
   Subclasses implement the GameView interface by extending Grid2DView and
   overriding drawEntities(ctx, s, geom) + optionally hudExtra(vm):
     render(vm, now), updateHud(vm), showOverlay/hideOverlay, dispose,
     plus no-op camera hooks so the shared SnakeInput gestures don't throw. */
(function () {
  const DEFAULT_COLORS = {
    bg: '#0b1020', grid: '#1c2740', text: '#e8ecff',
  };

  window.Grid2DView = class Grid2DView {
    constructor(canvas, colors) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.colors = Object.assign({}, DEFAULT_COLORS, colors || {});
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
      // keep the drawing buffer matched to the full-viewport canvas (the CSS
      // stretches the element to 100%; the buffer must match to stay sharp)
      this._onResize = () => this.resize();
      window.addEventListener('resize', this._onResize);
      this.resize();
    }

    resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = this.canvas.clientWidth || window.innerWidth;
      const h = this.canvas.clientHeight || window.innerHeight;
      this.canvas.width = Math.max(1, Math.round(w * dpr));
      this.canvas.height = Math.max(1, Math.round(h * dpr));
    }

    // no-op camera controls so the shared SnakeInput gestures don't throw
    zoomBy() {}
    rotateBy() {}
    getGroundBasis() { return { right: { x: 1, z: 0 }, forward: { x: 0, z: 1 } }; }

    showOverlay(title, msg, cta) {
      this.dom.ovTitle.textContent = title;
      this.dom.ovMsg.textContent = msg;
      this.dom.ovCta.textContent = cta;
      this.dom.overlay.classList.remove('hidden');
    }

    hideOverlay() { this.dom.overlay.classList.add('hidden'); }

    updateHud(vm) {
      const s = vm.state;
      if (!s) return;
      this.dom.score.textContent = s.score;
      this.dom.best.textContent = (vm.meta && vm.meta.best) || 0;
      if (this.dom.speed && document.activeElement !== this.dom.speed) {
        this.dom.speed.value = (vm.meta && vm.meta.stepTimeMs) || s.stepTimeMs || 260;
      }
      if (this.hudExtra) this.hudExtra(vm);
    }

    /* geometry helper: square board centered in the canvas */
    geom() {
      const c = this.canvas;
      const w = c.width || 400, h = c.height || 400;
      const size = Math.min(w, h);
      return { w, h, size, ox: (w - size) / 2, oy: (h - size) / 2 };
    }

    render(vm) {
      const s = vm.state;
      const c = this.canvas, ctx = this.ctx;
      const g = this.geom();
      ctx.fillStyle = this.colors.bg;
      ctx.fillRect(0, 0, g.w, g.h);
      if (!s || !s.gridSize) return;
      const n = s.gridSize, cell = g.size / n;
      ctx.strokeStyle = this.colors.grid;
      for (let i = 0; i <= n; i++) {
        ctx.beginPath(); ctx.moveTo(g.ox + i * cell, g.oy); ctx.lineTo(g.ox + i * cell, g.oy + g.size); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(g.ox, g.oy + i * cell); ctx.lineTo(g.ox + g.size, g.oy + i * cell); ctx.stroke();
      }
      const geom = { ox: g.ox, oy: g.oy, cell, size: g.size, n };
      this.drawEntities(ctx, s, geom);
    }

    /* subclasses override: draw game entities for state s */
    drawEntities(ctx, s, geom) {}

    dispose() {
      window.removeEventListener('resize', this._onResize);
    }
  };
})();
