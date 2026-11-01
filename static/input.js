/* Input — all keyboard/touch/wheel gestures, mapped to viewmodel actions
   and camera controls on the view. */
window.SnakeInput = class SnakeInput {
  constructor(vm, view, onStart) {
    this.vm = vm;
    this.view = view;
    this.onStart = onStart;
    this._touches = {};
    this._swipeStart = null;
    this._pinchDist = 0;
    this._pinched = false;
    this._lastMidX = null;
    this._lastTapTime = 0;
    this._bind();
  }

  _bind() {
    const vm = this.vm, view = this.view;
    /* Touch: swipe (rotated 45°) = horizontal, single tap = down,
       double tap = up, pinch/span = camera zoom */
    window.addEventListener('touchstart', (e) => {
      for (const t of e.changedTouches) this._touches[t.identifier] = { x: t.clientX, y: t.clientY };
      const ids = Object.keys(this._touches);
      if (ids.length === 1) { this._swipeStart = { ...this._touches[ids[0]] }; this._pinched = false; }
      if (ids.length === 2) {
        const a = this._touches[ids[0]], b = this._touches[ids[1]];
        this._pinchDist = Math.hypot(a.x - b.x, a.y - b.y);
      }
    }, { passive: true });
    window.addEventListener('touchmove', (e) => {
      e.preventDefault();
      for (const t of e.changedTouches) if (this._touches[t.identifier]) this._touches[t.identifier] = { x: t.clientX, y: t.clientY };
      const ids = Object.keys(this._touches);
      if (ids.length === 2) {
        const a = this._touches[ids[0]], b = this._touches[ids[1]];
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        if (this._pinchDist > 0) view.zoomBy(d / this._pinchDist);
        this._pinchDist = d;
        // two-finger sideways drag orbits the camera around the vertical axis
        const midX = (a.x + b.x) / 2;
        if (this._lastMidX !== null) view.rotateBy((midX - this._lastMidX) * 0.008);
        this._lastMidX = midX;
        this._pinched = true;
      }
    }, { passive: false });
    window.addEventListener('touchend', (e) => {
      const t = e.changedTouches[0];
      const ended = { x: t.clientX, y: t.clientY };
      for (const tt of e.changedTouches) delete this._touches[tt.identifier];
      const ids = Object.keys(this._touches);
      if (ids.length === 0 && this._swipeStart && !this._pinched) {
        const dx = ended.x - this._swipeStart.x, dy = ended.y - this._swipeStart.y;
        if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) {
          const now = performance.now();
          if (now - this._lastTapTime < 300) {
            this._lastTapTime = 0;
            if (vm.running) vm.queueDirection('up');
            else this.onStart();
          } else {
            this._lastTapTime = now;
            setTimeout(() => {
              if (performance.now() - this._lastTapTime >= 300) {
                if (vm.running) vm.queueDirection('down');
                else this.onStart();
              }
            }, 310);
          }
        } else if (vm.running) {
          // Rotate the screen-space gesture by the camera's yaw (ground-plane
          // basis) so swipes align with the cube for any rotation angle.
          const basis = view.getGroundBasis();
          const wx = basis.right.x * dx - basis.forward.x * dy;
          const wz = basis.right.z * dx - basis.forward.z * dy;
          if (Math.abs(wx) > Math.abs(wz)) vm.queueDirection(wx > 0 ? 'right' : 'left');
          else vm.queueDirection(wz > 0 ? 'forward' : 'back');
        }
      }
      if (ids.length < 2) { this._pinchDist = 0; this._lastMidX = null; }
      if (ids.length === 0) { this._swipeStart = null; this._pinched = false; }
    }, { passive: true });

    window.addEventListener('keydown', (e) => {
      const map = {
        ArrowUp: 'back', ArrowDown: 'forward', ArrowLeft: 'left', ArrowRight: 'right',
        PageUp: 'up', '+': 'up', '=': 'up', PageDown: 'down', '-': 'down',
      };
      // Player 2 (multiplayer): WASD + Q/E for up/down
      const mapP2 = {
        w: 'back', s: 'forward', a: 'left', d: 'right', q: 'up', e: 'down',
      };
      const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      if (mapP2[k] && vm.mode === 'multi') { e.preventDefault(); vm.queueDirection(mapP2[k], 1); return; }
      if (map[e.key]) { e.preventDefault(); vm.queueDirection(map[e.key]); }
    });
    window.addEventListener('wheel', (e) => {
      e.preventDefault();
      view.zoomBy(e.deltaY < 0 ? 0.9 : 1.1);
    }, { passive: false });
    window.addEventListener('contextmenu', (e) => e.preventDefault());
  }
};
