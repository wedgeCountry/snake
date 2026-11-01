/* Scene — Three.js scene construction (floor, box, lanes, food, segments),
   camera and resize handling. Rendering lives in view.js. */
window.SnakeScene = class SnakeScene {
  constructor(canvas) {
    this.N = 10;
    this.OFF = (this.N - 1) / 2;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputEncoding = THREE.sRGBEncoding;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0b1020);
    this.scene.fog = new THREE.Fog(0x0b1020, this.N * 3.2, this.N * 7);
    this.camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 300);
    this.zoomLevel = 1;
    this.orbitAngle = Math.PI / 4;

    this.scene.add(new THREE.AmbientLight(0x8899ff, 0.55));
    const sun = new THREE.DirectionalLight(0xffffff, 0.95);
    sun.position.set(0, this.N * 3, 0);
    sun.castShadow = true;
    sun.shadow.mapSize.width = sun.shadow.mapSize.height = 2048;
    const sc = this.N / 2 + 2;
    Object.assign(sun.shadow.camera, { left: -sc, right: sc, top: sc, bottom: -sc, far: this.N * 6 });
    this.scene.add(sun);

    this.fruitStyles = {
      apple:      { color: 0xff8c1a, emissive: 0xff5500 },
      reverse:    { color: 0x9b5cff, emissive: 0x6a1fd0 },
      grow_grid:  { color: 0x4dff88, emissive: 0x12b76a },
      shrink_grid:{ color: 0xff5c7a, emissive: 0xd0244a },
      star:       { color: 0xffe14d, emissive: 0xffc400 },
    };

    this._buildFloor();
    this._buildBox();
    this._buildLanes();
    this._buildFood();
    this._buildSegments();

    window.addEventListener('resize', () => {
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(window.innerWidth, window.innerHeight);
    });
  }

  _cell(c) { return c - this.OFF; }

  _buildFloor() {
    if (this.floor) {
      this.scene.remove(this.floor);
      this.floor.geometry.dispose();
      this.floor.material.map.dispose();
      this.floor.material.dispose();
    }
    const c = document.createElement('canvas');
    c.width = c.height = 512;
    const g = c.getContext('2d');
    const s = 512 / 8;
    for (let i = 0; i < 8; i++) for (let j = 0; j < 8; j++) {
      g.fillStyle = ((i + j) % 2 === 0) ? '#131a33' : '#0f1529';
      g.fillRect(i * s, j * s, s, s);
    }
    this.floor = new THREE.Mesh(
      new THREE.PlaneGeometry(this.N * 6, this.N * 6),
      new THREE.MeshStandardMaterial({ map: new THREE.CanvasTexture(c), roughness: 1 })
    );
    this.floor.rotation.x = -Math.PI / 2;
    this.floor.position.y = -this.OFF - 0.51;
    this.floor.receiveShadow = true;
    this.scene.add(this.floor);
  }

  _buildBox() {
    if (this.boxEdges) {
      this.scene.remove(this.boxEdges);
      this.boxEdges.geometry.dispose();
      this.scene.remove(this.levelLines);
    }
    this.boxEdges = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(this.N, this.N, this.N)),
      new THREE.LineBasicMaterial({ color: 0xff3355, transparent: true, opacity: 0.55 })
    );
    this.boxEdges.position.y = 0.5;
    this.scene.add(this.boxEdges);
    this.levelLines = new THREE.Group();
    for (let i = 1; i < this.N; i++) {
      const lg = new THREE.GridHelper(this.N, this.N, 0x2a3a66, 0x18224a);
      lg.position.y = i - this.OFF;
      lg.material.transparent = true;
      lg.material.opacity = 0.18;
      this.levelLines.add(lg);
    }
    this.scene.add(this.levelLines);
  }

  /* Rebuild board geometry when the server grows/shrinks the grid. */
  setGridSize(n) {
    if (n === this.N) return;
    this.N = n;
    this.OFF = (n - 1) / 2;
    this._buildFloor();
    this._buildBox();
    if (this.foodBlob) this.foodBlob.position.y = -this.OFF - 0.5;
    for (const p of this.blobShadows || []) for (const b of p) b.position.y = -this.OFF - 0.5;
  }

  _buildLanes() {
    this.lanes = [];
    [[1, 0, 0, 0x66b3ff], [0, 1, 0, 0x4d9fff], [0, 0, 1, 0x3385ff]].forEach((cfg) => {
      const m = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial({ color: cfg[3], transparent: true, opacity: 0.1, blending: THREE.AdditiveBlending, depthWrite: false })
      );
      m.userData.axis = { x: cfg[0], y: cfg[1], z: cfg[2] };
      this.scene.add(m);
      this.lanes.push(m);
    });
    this.fruitLanes = [];
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]].forEach((a) => {
      const m = new THREE.Mesh(
        new THREE.BoxGeometry(1, 1, 1),
        new THREE.MeshBasicMaterial({ color: 0xffe14d, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false })
      );
      m.userData.axis = { x: a[0], y: a[1], z: a[2] };
      this.scene.add(m);
      this.fruitLanes.push(m);
    });
  }

  _buildFood() {
    this.food = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.36, 0),
      new THREE.MeshStandardMaterial({ color: 0xff8c1a, emissive: 0xff5500, emissiveIntensity: 1.3, roughness: 0.25 })
    );
    this.food.castShadow = true;
    this.scene.add(this.food);
    this.foodLight = new THREE.PointLight(0xff7733, 1.2, 10);
    this.scene.add(this.foodLight);
    this.foodBlob = new THREE.Mesh(
      new THREE.CircleGeometry(0.42, 24),
      new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.35, depthWrite: false })
    );
    this.foodBlob.rotation.x = -Math.PI / 2;
    this.foodBlob.position.y = -this.OFF - 0.5;
    this.scene.add(this.foodBlob);
  }

  _buildSegments() {
    this.segGeo = new THREE.BoxGeometry(0.84, 0.84, 0.84);
    this.headGeo = new THREE.BoxGeometry(0.9, 0.9, 0.9);
    // one head material per player (P1 green, P2 orange)
    this.headMats = [
      new THREE.MeshStandardMaterial({ color: 0x7dff9b, emissive: 0x1fae4f, emissiveIntensity: 0.6, roughness: 0.3 }),
      new THREE.MeshStandardMaterial({ color: 0xffb35c, emissive: 0xd97316, emissiveIntensity: 0.6, roughness: 0.3 }),
    ];
    this.PLAYER_HUES = [0.36, 0.08]; // body gradient base per player
    this.segments = [[], []];
    this.blobShadows = [[], []];
    const blobGeo = new THREE.CircleGeometry(0.42, 24);
    for (let p = 0; p < 2; p++) {
      for (let i = 0; i < 64; i++) {
        const isHead = i === 0;
        const m = new THREE.Mesh(isHead ? this.headGeo : this.segGeo, isHead ? this.headMats[p] : new THREE.MeshStandardMaterial({ roughness: 0.35, metalness: 0.1 }));
        m.castShadow = true;
        if (isHead) m.rotation.order = 'YXZ';
        m.visible = false;
        this.scene.add(m);
        this.segments[p].push(m);
        const b = new THREE.Mesh(blobGeo, new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.35, depthWrite: false }));
        b.rotation.x = -Math.PI / 2;
        b.position.y = -this.OFF - 0.5;
        b.visible = false;
        this.scene.add(b);
        this.blobShadows[p].push(b);
      }
    }
  }

  ensureSegments(player, n) {
    const segs = this.segments[player] || this.segments[0];
    const blobs = this.blobShadows[player] || this.blobShadows[0];
    for (let i = 0; i < n; i++) segs[i].visible = true;
    for (let i = n; i < segs.length; i++) { segs[i].visible = false; blobs[i].visible = false; }
  }

  clearSegments() {
    for (let p = 0; p < this.segments.length; p++) this.ensureSegments(p, 0);
  }

  zoomBy(factor) {
    this.zoomLevel = Math.min(2.2, Math.max(0.5, this.zoomLevel * factor));
  }

  /* Orbit the camera around the vertical (Y) axis; the cube itself and its
     world Z axis stay fixed. */
  rotateBy(deltaAngle) {
    this.orbitAngle += deltaAngle;
  }

  /* Ground-plane (XZ) basis of the camera: screen-right and screen-forward
     as 2D world vectors. Applying these to a screen-space gesture vector is
     the rotational transform of the cube for any camera yaw. */
  getGroundBasis() {
    const fwd = new THREE.Vector3();
    this.camera.getWorldDirection(fwd);
    const fx = fwd.x, fz = fwd.z;
    const len = Math.hypot(fx, fz) || 1;
    const forward = { x: fx / len, z: fz / len };
    const right = { x: -forward.z, z: forward.x };
    return { right, forward };
  }

  updateCamera(now) {
    this.boxEdges.material.opacity = this._torus ? 0.22 : 0.55;
    const sway = Math.sin(now * 0.0002) * 0.6 * this.zoomLevel;
    const z = this.zoomLevel;
    const r = this.N * 1.35;
    this.camera.position.set(
      (r * Math.sin(this.orbitAngle) + sway) * z,
      this.N * 1.5 * z,
      (r * Math.cos(this.orbitAngle) - sway) * z
    );
    this.camera.lookAt(0, 0.5, 0);
  }

  render() {
    this.renderer.render(this.scene, this.camera);
  }
};
