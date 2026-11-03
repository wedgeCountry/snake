/* Dungeon Quest view — 2D canvas rendering of the RPG.
   Implements the GameView interface: render(vm, now), updateHud(vm),
   showOverlay, hideOverlay, dispose. */
(function () {
  const COLORS = {
    bg: '#0b1020', grid: '#241a2e', hero: '#4dff88', monster: '#ff5c7a',
    boss: '#b3123f', potion: '#4dd0ff', text: '#e8ecff',
  };

  window.GameView_dungeon = class DungeonView {
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
      this.dom.height.textContent = (s.hero ? s.hero.hp : 0) + ' HP';
      if (this.dom.star) {
        this.dom.star.style.display = s.hero ? '' : 'none';
        this.dom.star.textContent = 'Lvl ' + (s.hero ? s.hero.level : 1) + ' · ' + (s.hero ? s.hero.dmg : 0) + ' DMG';
      }
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
      ctx.fillStyle = COLORS.potion;
      for (const p of s.potions || []) {
        ctx.beginPath();
        ctx.arc(ox + (p[0] + 0.5) * cell, oy + (p[1] + 0.5) * cell, cell * 0.2, 0, 7);
        ctx.fill();
      }
      for (const m of s.monsters || []) {
        const r = m.kind === 'boss' ? cell * 0.4 : cell * 0.28;
        ctx.fillStyle = m.kind === 'boss' ? COLORS.boss : COLORS.monster;
        ctx.beginPath();
        ctx.arc(ox + (m.x + 0.5) * cell, oy + (m.y + 0.5) * cell, r, 0, 7);
        ctx.fill();
        ctx.fillStyle = '#000';
        ctx.fillRect(ox + m.x * cell + 2, oy + m.y * cell + 2, (cell - 4) * Math.max(0, m.hp) / (m.kind === 'boss' ? 30 : 8), 3);
      }
      const hero = s.hero;
      if (hero) {
        ctx.fillStyle = COLORS.hero;
        ctx.beginPath();
        ctx.arc(ox + (hero.x + 0.5) * cell, oy + (hero.y + 0.5) * cell, cell * 0.32, 0, 7);
        ctx.fill();
        ctx.fillStyle = COLORS.text;
        ctx.font = '12px sans-serif';
        ctx.fillText('HP ' + hero.hp + '/' + hero.max_hp + ' · XP ' + hero.xp + ' · Gold ' + hero.gold,
          ox + 6, oy + size + 18 > h ? oy - 6 : oy + size + 18);
      }
    }

    dispose() {}
  };
})();
