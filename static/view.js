/* View — pure rendering of ViewModel state into the Three.js scene. */
window.SnakeView = class SnakeView {
  constructor(canvas) {
    this.scene = new SnakeScene(canvas);
    this.hud = new SnakeHud();
  }

  get dom() { return this.hud.dom; }

  _cell(c) { return this.scene._cell(c); }

  _ensureSegments(player, n) { this.scene.ensureSegments(player, n); }

  zoomBy(factor) { this.scene.zoomBy(factor); }

  rotateBy(deltaAngle) { this.scene.rotateBy(deltaAngle); }

  getGroundBasis() { return this.scene.getGroundBasis(); }

  showOverlay(title, msg, cta) { this.hud.showOverlay(title, msg, cta); }

  hideOverlay() { this.hud.hideOverlay(); }

  updateHud(vm) { this.hud.update(vm); }

  render(vm, now) {
    const sc = this.scene;
    const s = vm.state;
    if (!s) return;
    sc._torus = vm.torus;
    if (s.gridSize && s.gridSize !== sc.N) sc.setGridSize(s.gridSize);
    const snakes = s.snakes || [s.snake];
    const directions = s.directions || [s.direction];
    const numPlayers = snakes.length;
    sc.clearSegments();
    for (let p = 0; p < numPlayers; p++) {
      const snake = snakes[p];
      const hue = sc.PLAYER_HUES[p % sc.PLAYER_HUES.length];
      this._ensureSegments(p, snake.length);
      for (let i = 0; i < snake.length; i++) {
        const seg = snake[i];
        sc.segments[p][i].position.set(this._cell(seg.x), this._cell(seg.y) + 0.5, this._cell(seg.z));
        if (i > 0) {
          const f = i / Math.max(1, snake.length - 1);
          sc.segments[p][i].material.color.setHSL(hue - f * 0.10, 0.85, 0.55 - f * 0.25);
        }
        const sy = seg.y - (sc.N - 1) / 2;
        const sf = 1 + (sy + sc.OFF) / sc.N * 0.5;
        sc.blobShadows[p][i].visible = true;
        sc.blobShadows[p][i].position.x = sc.segments[p][i].position.x;
        sc.blobShadows[p][i].position.z = sc.segments[p][i].position.z;
        sc.blobShadows[p][i].scale.set(sf, sf, sf);
        sc.blobShadows[p][i].material.opacity = 0.30 + 0.14 * (sf - 1);
      }
      const d = directions[p] || s.direction;
      sc.segments[p][0].rotation.set(-d.y * Math.PI / 2, Math.atan2(d.x, d.z), 0);
    }

    const pulse = 0.05 + Math.sin(now * 0.004) * 0.02;
    const h = snakes[0][0];
    const hx = this._cell(h.x), hy = this._cell(h.y) + 0.5, hz = this._cell(h.z);
    const d = directions[0] || s.direction;
    sc.lanes.forEach((lane) => {
      const a = lane.userData.axis;
      const isDir = a.x === d.x && a.y === d.y && a.z === d.z;
      const hitsFruit = a.x ? (h.y === s.food.y && h.z === s.food.z)
        : a.y ? (h.x === s.food.x && h.z === s.food.z)
        : (h.x === s.food.x && h.y === s.food.y);
      lane.scale.set(a.x ? sc.N : 0.7, a.y ? sc.N : 0.7, a.z ? sc.N : 0.7);
      lane.position.set(a.x ? 0 : hx, a.y ? 0.5 : hy, a.z ? 0 : hz);
      lane.material.opacity = hitsFruit ? 0.55 : (isDir ? pulse * 2.2 : pulse);
      lane.material.color.setHex(hitsFruit ? 0xff2244 : (a.x ? 0x66b3ff : a.y ? 0x4d9fff : 0x3385ff));
    });

    const f = s.food;
    const style = sc.fruitStyles[f.kind] || sc.fruitStyles.apple;
    for (const kind of Object.keys(sc.fruitMeshes)) {
      const m = sc.fruitMeshes[kind];
      m.visible = kind === f.kind;
      if (m.visible) {
        m.material.color.setHex(style.color);
        m.material.emissive.setHex(style.emissive);
        m.material.emissiveIntensity = 1.3;
      }
    }
    sc.foodLight.color.setHex(style.emissive);
    sc.food.position.set(this._cell(f.x), this._cell(f.y) + 0.5, this._cell(f.z));
    sc.foodLight.position.set(this._cell(f.x), this._cell(f.y) + 1.2, this._cell(f.z));
    const starActive = (s.starSteps && s.starSteps[0] > 0);
    const p = f.kind === 'star' || starActive
      ? 1.25 + Math.sin(now * 0.008) * 0.3
      : 1 + Math.sin(now * 0.005) * 0.15;
    sc.food.scale.set(p, p, p);
    sc.food.rotation.y += f.kind === 'star' ? 0.012 : 0.003;
    const fx = this._cell(f.x), fy = this._cell(f.y) + 0.5, fz = this._cell(f.z);
    const fsf = 1 + (f.y - (sc.N - 1) / 2 + sc.OFF) / sc.N * 0.5;
    sc.foodBlob.position.x = fx;
    sc.foodBlob.position.z = fz;
    sc.foodBlob.scale.set(fsf, fsf, fsf);
    sc.fruitLanes.forEach((fl) => {
      const a = fl.userData.axis;
      fl.scale.set(a.x ? sc.N : 0.7, a.y ? sc.N : 0.7, a.z ? sc.N : 0.7);
      fl.position.set(a.x ? 0 : fx, a.y ? 0.5 : fy, a.z ? 0 : fz);
      fl.material.opacity = 0.13 + Math.sin(now * 0.004 + 1.3) * 0.05;
    });

    sc.updateCamera(now);
    sc.render();
  }
};
