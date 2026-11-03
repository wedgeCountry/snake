/* Collector view — thin subclass of the shared 2D grid view. */
(function () {
  const COLORS = { dot: '#ffe14d', pos: '#4dff88' };

  window.GameView_collector = class CollectorView extends window.Grid2DView {
    constructor(canvas) {
      super(canvas);
    }

    updateHud(vm) {
      if (!vm.state) return;
      this.dom.best.textContent = vm.state.best || 0;
      super.updateHud(vm);
    }

    drawEntities(ctx, s, geom) {
      const { ox, oy, cell } = geom;
      ctx.fillStyle = COLORS.dot;
      for (const d of s.dots || []) {
        ctx.beginPath();
        ctx.arc(ox + (d[0] + 0.5) * cell, oy + (d[1] + 0.5) * cell, cell * 0.3, 0, 7);
        ctx.fill();
      }
      ctx.fillStyle = COLORS.pos;
      ctx.fillRect(ox + s.pos[0] * cell + 2, oy + s.pos[1] * cell + 2, cell - 4, cell - 4);
    }
  };
})();
