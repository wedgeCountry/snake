/* Dungeon Quest view — party RPG on the shared 2D grid view: the hero party
   moves as one marker, the HUD lists every member's hp/ac. */
(function () {
  const COLORS = { party: ['#4dff88', '#ffd54d', '#4dd0ff'], monster: '#ff5c7a', boss: '#b3123f', potion: '#4dd0ff', log: '#aab6e8' };

  window.GameView_dungeon = class DungeonView extends window.Grid2DView {
    constructor(canvas) {
      super(canvas, { grid: '#241a2e' });
    }

    hudExtra(vm) {
      const s = vm.state;
      const party = s.party || [];
      const hp = party.reduce((a, m) => a + (m.hp || 0), 0);
      const maxHp = party.reduce((a, m) => a + (m.max_hp || 0), 0);
      this.dom.height.textContent = hp + '/' + maxHp + ' HP';
      if (this.dom.star) {
        const gold = (party[0] && party[0].gold) || 0;
        this.dom.star.style.display = '';
        this.dom.star.textContent = 'Lv ' + (party[0] ? party[0].level : 1) + ' · Gold ' + gold + ' · [E] verzaubern';
      }
    }

    drawEntities(ctx, s, geom) {
      const { ox, oy, cell, size } = geom;
      ctx.fillStyle = '#3a2c4f';
      for (const w of s.walls || []) {
        ctx.fillRect(ox + w[0] * cell, oy + w[1] * cell, cell, cell);
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
        const maxHp = m.max_hp || (m.kind === 'boss' ? 30 : 8);
        ctx.fillRect(ox + m.x * cell + 2, oy + m.y * cell + 2,
          (cell - 4) * Math.max(0, m.hp) / maxHp, 3);
        ctx.fillStyle = this.colors.text;
        ctx.font = '10px sans-serif';
        ctx.fillText('Lv' + (m.level || 1), ox + m.x * cell + 2, oy + (m.y + 1) * cell - 3);
      }
      const party = s.party || [];
      const leader = party[0];
      if (leader) {
        // the party moves as a unit: one marker per member, fanned in the cell
        party.forEach((m, i) => {
          const dx = (i - (party.length - 1) / 2) * cell * 0.24;
          ctx.fillStyle = COLORS.party[i % COLORS.party.length];
          ctx.beginPath();
          ctx.arc(ox + (leader.x + 0.5) * cell + dx, oy + (leader.y + 0.5) * cell, cell * 0.14, 0, 7);
          ctx.fill();
        });
        ctx.fillStyle = this.colors.text;
        ctx.font = '12px sans-serif';
        const members = party.map((m) => {
          const w = m.weapon || {};
          const ench = w.enchant ? ' [' + w.enchant.name + ']' : '';
          return m.name + ' ' + m.hp + '/' + m.max_hp + ' HP · AC ' + (m.ac || 10) + ' · ' + (w.name || '—') + ench;
        }).join('  |  ');
        ctx.fillText('Dungeon D' + (s.difficulty || 5) + ' (gemessen ' + (s.levelDifficulty || 5) + ') · Gold ' +
          (leader.gold || 0) + ' · ' + members + ' · [E] verzaubern',
          ox + 6, oy + size + 18);
      }
      ctx.fillStyle = COLORS.log;
      ctx.font = '11px sans-serif';
      (s.combatLog || []).slice(-4).forEach((line, i) => {
        ctx.fillText(line, ox + 6, oy + 16 + i * 14);
      });
    }
  };
})();
