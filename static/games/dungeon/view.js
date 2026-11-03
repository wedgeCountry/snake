/* Dungeon Quest view — thin subclass of the shared 2D grid view. */
(function () {
  const COLORS = { hero: '#4dff88', monster: '#ff5c7a', boss: '#b3123f', potion: '#4dd0ff' };

  window.GameView_dungeon = class DungeonView extends window.Grid2DView {
    constructor(canvas) {
      super(canvas, { grid: '#241a2e' });
    }

    hudExtra(vm) {
      const s = vm.state;
      const hero = s.hero || {};
      this.dom.height.textContent = hero.hp + ' HP';
      if (this.dom.star) {
        this.dom.star.style.display = '';
        this.dom.star.textContent = 'Lvl ' + (hero.level || 1) + ' · ' + (hero.dmg || 0) + ' DMG';
      }
    }

    drawEntities(ctx, s, geom) {
      const { ox, oy, cell, size } = geom;
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
        ctx.fillRect(ox + m.x * cell + 2, oy + m.y * cell + 2,
          (cell - 4) * Math.max(0, m.hp) / (m.kind === 'boss' ? 30 : 8), 3);
      }
      const hero = s.hero;
      if (hero) {
        ctx.fillStyle = COLORS.hero;
        ctx.beginPath();
        ctx.arc(ox + (hero.x + 0.5) * cell, oy + (hero.y + 0.5) * cell, cell * 0.32, 0, 7);
        ctx.fill();
        ctx.fillStyle = this.colors.text;
        ctx.font = '12px sans-serif';
        ctx.fillText('HP ' + hero.hp + '/' + hero.max_hp + ' · XP ' + hero.xp + ' · Gold ' + hero.gold, ox + 6, oy + size + 18);
      }
    }
  };
})();
