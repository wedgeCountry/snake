/* Dungeon Quest view — the dungeon game's own canvas: a checkerboard dungeon
   floor with wall blocks, class-colored party tokens, monster tokens with HP
   bars, a combat log and a party stats bar. A "Stats" button opens a details
   panel for the party; tapping an enemy (or the party) shows its stats. */
(function () {
  const CLASS_COLORS = { warrior: '#4dff88', mage: '#ffd54d', cleric: '#4dd0ff' };
  const COLORS = {
    floorA: '#1a1226', floorB: '#211832', wall: '#3a2c4f', border: '#4a3670',
    monster: '#ff5c7a', boss: '#b3123f', potion: '#4dd0ff', log: '#aab6e8',
    hp: '#7dff9b', hpBg: '#402030', barBg: '#241a2e',
  };

  window.GameView_dungeon = class DungeonView extends window.Grid2DView {
    constructor(canvas) {
      super(canvas, { bg: '#120b1c', grid: '#2c2140', text: '#e8ecff' });
      this._n = 8;
      this._state = null;
      this._makePanel();
      this._onPointer = (e) => this._handleTap(e);
      canvas.addEventListener('pointerdown', this._onPointer);
    }

    _makePanel() {
      this.statsBtn = document.createElement('button');
      this.statsBtn.type = 'button';
      this.statsBtn.className = 'dungeon-stats-btn';
      this.statsBtn.textContent = 'Stats';
      this.statsBtn.addEventListener('click', (e) => { e.stopPropagation(); this._toggleStats(); });
      document.body.appendChild(this.statsBtn);
      this.panel = document.createElement('div');
      this.panel.className = 'dungeon-panel hidden';
      document.body.appendChild(this.panel);
    }

    dispose() {
      this.canvas.removeEventListener('pointerdown', this._onPointer);
      if (this.statsBtn) this.statsBtn.remove();
      if (this.panel) this.panel.remove();
      super.dispose();
    }

    hudExtra(vm) {
      const s = vm.state;
      const party = (s && s.party) || [];
      const hp = party.reduce((a, m) => a + (m.hp || 0), 0);
      const maxHp = party.reduce((a, m) => a + (m.max_hp || 0), 0);
      this.dom.height.textContent = hp + '/' + maxHp + ' HP';
      if (this.dom.star) {
        const leader = party[0] || {};
        this.dom.star.style.display = '';
        this.dom.star.textContent = 'Lv ' + (leader.level || 1) + ' · XP ' + (leader.xp || 0) +
          '/' + (leader.xpNeeded || '?') + ' · Gold ' + (leader.gold || 0);
      }
    }

    render(vm) {
      const s = vm.state;
      const c = this.canvas, ctx = this.ctx;
      const g = this.geom();
      ctx.fillStyle = this.colors.bg;
      ctx.fillRect(0, 0, g.w, g.h);
      if (!s || !s.gridSize) return;
      this._state = s;
      this._n = s.gridSize;
      const n = s.gridSize, cell = g.size / n;
      // checkerboard dungeon floor + border (own look, not the shared plain grid)
      for (let x = 0; x < n; x++) {
        for (let y = 0; y < n; y++) {
          ctx.fillStyle = (x + y) % 2 ? COLORS.floorA : COLORS.floorB;
          ctx.fillRect(g.ox + x * cell, g.oy + y * cell, cell, cell);
        }
      }
      ctx.strokeStyle = COLORS.border;
      ctx.lineWidth = 3;
      ctx.strokeRect(g.ox, g.oy, g.size, g.size);
      this.drawEntities(ctx, s, { ox: g.ox, oy: g.oy, cell, size: g.size, n });
    }

    drawEntities(ctx, s, geom) {
      const { ox, oy, cell } = geom;
      // walls as solid blocks with a bevel
      for (const w of s.walls || []) {
        ctx.fillStyle = COLORS.wall;
        ctx.fillRect(ox + w[0] * cell, oy + w[1] * cell, cell, cell);
        ctx.strokeStyle = COLORS.border;
        ctx.lineWidth = 2;
        ctx.strokeRect(ox + w[0] * cell + 2, oy + w[1] * cell + 2, cell - 4, cell - 4);
      }
      // potions
      ctx.fillStyle = COLORS.potion;
      for (const p of s.potions || []) {
        ctx.beginPath();
        ctx.arc(ox + (p[0] + 0.5) * cell, oy + (p[1] + 0.5) * cell, cell * 0.2, 0, 7);
        ctx.fill();
      }
      // monsters / boss with hp bar + level
      for (const m of s.monsters || []) {
        const isBoss = m.kind === 'boss';
        ctx.fillStyle = isBoss ? COLORS.boss : COLORS.monster;
        ctx.beginPath();
        ctx.arc(ox + (m.x + 0.5) * cell, oy + (m.y + 0.5) * cell, cell * (isBoss ? 0.4 : 0.28), 0, 7);
        ctx.fill();
        ctx.fillStyle = '#000';
        ctx.fillRect(ox + m.x * cell + 2, oy + m.y * cell + 2,
          (cell - 4) * Math.max(0, m.hp) / (m.max_hp || 1), 3);
        ctx.fillStyle = this.colors.text;
        ctx.font = '10px sans-serif';
        ctx.fillText('Lv' + (m.level || 1), ox + m.x * cell + 2, oy + (m.y + 1) * cell - 3);
      }
      // the party: one class-colored token per member, fanned in the leader's cell
      const party = s.party || [];
      const leader = party[0];
      if (leader) {
        party.forEach((m, i) => {
          const dx = (i - (party.length - 1) / 2) * cell * 0.24;
          ctx.fillStyle = CLASS_COLORS[m.class] || '#4dff88';
          ctx.beginPath();
          ctx.arc(ox + (leader.x + 0.5) * cell + dx, oy + (leader.y + 0.5) * cell, cell * 0.15, 0, 7);
          ctx.fill();
          ctx.fillStyle = '#000';
          ctx.font = 'bold ' + Math.round(cell * 0.16) + 'px sans-serif';
          ctx.fillText((m.name || '?')[0], ox + (leader.x + 0.5) * cell + dx - cell * 0.05,
            oy + (leader.y + 0.5) * cell + cell * 0.06);
        });
      }
      // combat log, top-left over the board
      ctx.fillStyle = COLORS.log;
      ctx.font = '11px sans-serif';
      (s.combatLog || []).slice(-4).forEach((line, i) => {
        ctx.fillText(line, ox + 6, oy + 16 + i * 14);
      });
      // party stats bar along the bottom of the board: name, Lv, hp bar
      const barH = Math.max(26, cell * 0.55);
      const by = oy + geom.size - barH;
      ctx.fillStyle = 'rgba(10,6,18,0.85)';
      ctx.fillRect(ox, by, geom.size, barH);
      party.forEach((m, i) => {
        const bw = geom.size / Math.max(1, party.length);
        const bx = ox + i * bw + 6;
        const w = (m.weapon || {});
        const ench = w.enchant ? ' [' + w.enchant.name + ']' : '';
        ctx.fillStyle = CLASS_COLORS[m.class] || '#4dff88';
        ctx.beginPath();
        ctx.arc(bx + 6, by + barH / 2, 5, 0, 7);
        ctx.fill();
        ctx.fillStyle = this.colors.text;
        ctx.font = '11px sans-serif';
        ctx.fillText(m.name + ' · Lv' + (m.level || 1) + ' · AC ' + (m.ac || 10) + ' · ' +
          (w.name || '—') + ench, bx + 16, by + 12);
        // hp bar
        ctx.fillStyle = COLORS.barBg;
        ctx.fillRect(bx + 16, by + barH - 9, bw - 24, 6);
        ctx.fillStyle = COLORS.hp;
        ctx.fillRect(bx + 16, by + barH - 9,
          (bw - 24) * Math.max(0, m.hp || 0) / (m.max_hp || 1), 6);
        ctx.fillStyle = this.colors.text;
        ctx.font = '10px sans-serif';
        ctx.fillText((m.hp || 0) + '/' + (m.max_hp || 0) + ' HP · XP ' + (m.xp || 0) + '/' +
          (m.xpNeeded || '?'), bx + 16, by + barH - 12);
      });
    }

    /* --- tap-to-inspect + stats panel --- */

    _cellAt(clientX, clientY) {
      const rect = this.canvas.getBoundingClientRect();
      const x = (clientX - rect.left) * (this.canvas.width / (rect.width || 1));
      const y = (clientY - rect.top) * (this.canvas.height / (rect.height || 1));
      const g = this.geom();
      const n = this._n, cell = g.size / n;
      const cx = Math.floor((x - g.ox) / cell);
      const cy = Math.floor((y - g.oy) / cell);
      return (cx >= 0 && cx < n && cy >= 0 && cy < n) ? [cx, cy] : null;
    }

    _handleTap(e) {
      const s = this._state;
      if (!s || !s.gridSize) return;
      const cell = this._cellAt(e.clientX, e.clientY);
      if (!cell) { this._hidePanel(); return; }
      const monster = (s.monsters || []).find((m) => m.x === cell[0] && m.y === cell[1]);
      if (monster) { this._showMonster(monster); return; }
      const leader = (s.party || [])[0];
      if (leader && leader.x === cell[0] && leader.y === cell[1]) { this._showParty(); return; }
      this._hidePanel();
    }

    _toggleStats() {
      if (this.panel && !this.panel.classList.contains('hidden')) this._hidePanel();
      else this._showParty();
    }

    _hidePanel() {
      if (this.panel) this.panel.classList.add('hidden');
    }

    _showPanel(html) {
      if (!this.panel) return;
      this.panel.innerHTML = html;
      this.panel.classList.remove('hidden');
    }

    _actorRows(a) {
      const w = a.weapon || {};
      const ench = w.enchant ? ' [' + w.enchant.name + ']' : '';
      const traits = (a.traits || []).map((t) => t.name).join(', ') || '—';
      const skills = (a.skills || []).map((t) => t.name).join(', ') || '—';
      return '<tr><td>HP</td><td>' + (a.hp || 0) + '/' + (a.max_hp || 0) + '</td></tr>' +
        '<tr><td>Level</td><td>' + (a.level || 1) +
        (a.xp !== undefined ? ' · XP ' + a.xp + '/' + (a.xpNeeded || '?') : '') + '</td></tr>' +
        '<tr><td>AC / ATK</td><td>' + (a.ac || 10) + ' / +' + (a.attack || 0) + '</td></tr>' +
        '<tr><td>Waffe</td><td>' + (w.name || '—') + ' (1W' + (w.die || 4) + '+' + (w.bonus || 0) + ')' + ench + '</td></tr>' +
        '<tr><td>Traits</td><td>' + traits + '</td></tr>' +
        '<tr><td>Skills</td><td>' + skills + '</td></tr>';
    }

    _showParty() {
      const party = (this._state && this._state.party) || [];
      const gold = (party[0] && party[0].gold) || 0;
      let html = '<h2>Gruppe</h2><p>Gold: ' + gold + '</p>';
      for (const m of party) {
        html += '<h3 style="color:' + (CLASS_COLORS[m.class] || '#4dff88') + '">' +
          m.name + (m.class ? ' (' + m.class + ')' : '') + '</h3>' +
          '<table class="dungeon-stats">' + this._actorRows(m) + '</table>';
      }
      this._showPanel(html);
    }

    _showMonster(m) {
      const html = '<h2 style="color:' + (m.kind === 'boss' ? COLORS.boss : COLORS.monster) + '">' +
        m.name + (m.kind === 'boss' ? ' (Boss)' : '') + '</h2>' +
        '<table class="dungeon-stats">' + this._actorRows(m) + '</table>';
      this._showPanel(html);
    }
  };
})();
