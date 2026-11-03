/* Territory view — 2D canvas rendering of the strategy game.
   Implements the GameView interface: render(vm, now), updateHud(vm),
   showOverlay, hideOverlay, dispose. */
(function () {
  const COLORS = {
    bg: '#0b1020', grid: '#1c2740', territory: '#2f6f4f', territoryEdge: '#4dff88',
    mine: '#ffe14d', settler: '#e8ecff', text: '#e8ecff',
  };

  window.GameView_territory = class TerritoryView {
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
      this.dom.height.textContent = s.turn + '/' + s.maxTurns;
    }

    render(vm) {
      const s = vm.state;
      const c = this.canvas, ctx = this.ctx;
      const w = c.width || 400, h = c.height || 400;
      ctx.fillStyle = COLORS.bg;
      ctx.fillRect(0, 0, w, h);
      if (!s || !s.gridSize) return;
      const n = s.gridSize, size = Math.min(w, h), cell = size / n;
      const ox = (w - size) / 2, oy = (h - size) / 2;
      ctx.strokeStyle = COLORS.grid;
      for (let i = 0; i <= n; i++) {
        ctx.beginPath(); ctx.moveTo(ox + i * cell, oy); ctx.lineTo(ox + i * cell, oy + size); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(ox, oy + i * cell); ctx.lineTo(ox + size, oy + i * cell); ctx.stroke();
      }
      const terr = new Set((s.territory || []).map((p) => p[0] + ',' + p[1]));
      const mines = new Set((s.mines || []).map((p) => p[0] + ',' + p[1]));
      ctx.fillStyle = COLORS.territory;
      for (const key of terr) {
        const [x, y] = key.split(',').map(Number);
        ctx.fillRect(ox + x * cell + 1, oy + y * cell + 1, cell - 2, cell - 2);
      }
      ctx.fillStyle = COLORS.mine;
      for (const key of mines) {
        const [x, y] = key.split(',').map(Number);
        ctx.beginPath();
        ctx.arc(ox + (x + 0.5) * cell, oy + (y + 0.5) * cell, cell * 0.22, 0, 7);
        ctx.fill();
      }
      if (s.pos) {
        ctx.fillStyle = COLORS.settler;
        ctx.beginPath();
        ctx.arc(ox + (s.pos[0] + 0.5) * cell, oy + (s.pos[1] + 0.5) * cell, cell * 0.32, 0, 7);
        ctx.fill();
        ctx.strokeStyle = COLORS.territoryEdge;
        ctx.stroke();
      }
      ctx.fillStyle = COLORS.text;
      ctx.font = '13px sans-serif';
      ctx.fillText('Gold: ' + s.gold + '  ·  Land: ' + terr.size + '/' + s.goal, ox + 6, oy + size + 18 > h ? oy - 6 : oy + size + 18);
    }

    dispose() {}
  };
})();
