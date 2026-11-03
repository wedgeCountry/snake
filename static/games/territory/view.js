/* Territory view — thin subclass of the shared 2D grid view. */
(function () {
  const COLORS = { territory: '#2f6f4f', territoryEdge: '#4dff88', mine: '#ffe14d', settler: '#e8ecff' };

  window.GameView_territory = class TerritoryView extends window.Grid2DView {
    constructor(canvas) {
      super(canvas, { grid: '#1c2740' });
    }

    hudExtra(vm) {
      const s = vm.state;
      this.dom.height.textContent = s.turn + '/' + s.maxTurns;
    }

    drawEntities(ctx, s, geom) {
      const { ox, oy, cell, size, n } = geom;
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
      ctx.fillStyle = this.colors.text;
      ctx.font = '13px sans-serif';
      ctx.fillText('Gold: ' + s.gold + '  ·  Land: ' + terr.size + '/' + s.goal, ox + 6, oy + size + 18);
    }
  };
})();
