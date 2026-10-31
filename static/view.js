/* View — pure rendering of ViewModel state into Three.js scene + DOM. */
window.SnakeView = class SnakeView {
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

    this.scene.add(new THREE.AmbientLight(0x8899ff, 0.55));
    const sun = new THREE.DirectionalLight(0xffffff, 0.95);
    sun.position.set(0, this.N * 3, 0);
    sun.castShadow = true;
    sun.shadow.mapSize.width = sun.shadow.mapSize.height = 2048;
    const sc = this.N / 2 + 2;
    Object.assign(sun.shadow.camera, { left: -sc, right: sc, top: sc, bottom: -sc, far: this.N * 6 });
    this.scene.add(sun);

    this._buildFloor();
    this._buildBox();
    this._buildLanes();
    this._buildFood();
    this._buildSegments();

    this.dom = {
      score: document.getElementById('score'),
      best: document.getElementById('best'),
      height: document.getElementById('height'),
      torusBtn: document.getElementById('torusBtn'),
      speed: document.getElementById('speed'),
      overlay: document.getElementById('overlay'),
      ovTitle: document.getElementById('ovTitle'),
      ovMsg: document.getElementById('ovMsg'),
      ovCta: document.getElementById('ovCta'),
    };
    window.addEventListener('resize', () => {
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(window.innerWidth, window.innerHeight);
    });
  }

  _cell(c) { return c - this.OFF; }

  _buildFloor() {
    const c = document.createElement('canvas');
    c.width = c.height = 512;
    const g = c.getContext('2d');
    const s = 512 / 8;
    for (let i = 0; i < 8; i++) for (let j = 0; j < 8; j++) {
      g.fillStyle = ((i + j) % 2 === 0) ? '#131a33' : '#0f1529';
      g.fillRect(i * s, j * s, s, s);
    }
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(this.N * 6, this.N * 6),
      new THREE.MeshStandardMaterial({ map: new THREE.CanvasTexture(c), roughness: 1 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -this.OFF - 0.51;
    floor.receiveShadow = true;
    this.scene.add(floor);
  }

  _buildBox() {
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
    this.headMat = new THREE.MeshStandardMaterial({ color: 0x7dff9b, emissive: 0x1fae4f, emissiveIntensity: 0.6, roughness: 0.3 });
    this.segments = [];
    this.blobShadows = [];
    const blobGeo = new THREE.CircleGeometry(0.42, 24);
    for (let i = 0; i < 64; i++) {
      const isHead = i === 0;
      const m = new THREE.Mesh(isHead ? this.headGeo : this.segGeo, isHead ? this.headMat : new THREE.MeshStandardMaterial({ roughness: 0.35, metalness: 0.1 }));
      m.castShadow = true;
      if (isHead) m.rotation.order = 'YXZ';
      m.visible = false;
      this.scene.add(m);
      this.segments.push(m);
      const b = new THREE.Mesh(blobGeo, new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.35, depthWrite: false }));
      b.rotation.x = -Math.PI / 2;
      b.position.y = -this.OFF - 0.5;
      b.visible = false;
      this.scene.add(b);
      this.blobShadows.push(b);
    }
  }

  _ensureSegments(n) {
    for (let i = 0; i < n; i++) this.segments[i].visible = true;
    for (let i = n; i < this.segments.length; i++) { this.segments[i].visible = false; this.blobShadows[i].visible = false; }
  }

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
    this.dom.best.textContent = s.best || 0;
    this.dom.height.textContent = s.snake[0].y - Math.floor(s.gridSize / 2) + (s.gridSize % 2 === 0 ? 0 : 0);
    this.dom.height.textContent = s.snake[0].y;
    this.dom.torusBtn.textContent = 'Torus: ' + (vm.torus ? 'An' : 'Aus');
    if (document.activeElement !== this.dom.speed) this.dom.speed.value = s.stepTimeMs;
  }

  render(vm, now) {
    const s = vm.state;
    if (!s) return;
    const t = vm.interpolation();
    this._ensureSegments(s.snake.length);
    for (let i = 0; i < s.snake.length; i++) {
      const seg = s.snake[i];
      this.segments[i].position.set(this._cell(seg.x), this._cell(seg.y) + 0.5, this._cell(seg.z));
      if (i > 0) {
        const f = i / Math.max(1, s.snake.length - 1);
        this.segments[i].material.color.setHSL(0.36 - f * 0.10, 0.85, 0.55 - f * 0.25);
      }
      const sy = seg.y - (this.N - 1) / 2;
      const sf = 1 + (sy + this.OFF) / this.N * 0.5;
      this.blobShadows[i].visible = true;
      this.blobShadows[i].position.x = this.segments[i].position.x;
      this.blobShadows[i].position.z = this.segments[i].position.z;
      this.blobShadows[i].scale.set(sf, sf, sf);
      this.blobShadows[i].material.opacity = 0.30 + 0.14 * (sf - 1);
    }
    const d = s.direction;
    this.segments[0].rotation.set(-d.y * Math.PI / 2, Math.atan2(d.x, d.z), 0);

    const pulse = 0.05 + Math.sin(now * 0.004) * 0.02;
    const h = s.snake[0];
    const hx = this._cell(h.x), hy = this._cell(h.y) + 0.5, hz = this._cell(h.z);
    this.lanes.forEach((lane, li) => {
      const a = lane.userData.axis;
      const isDir = a.x === d.x && a.y === d.y && a.z === d.z;
      const hitsFruit = a.x ? (h.y === s.food.y && h.z === s.food.z)
        : a.y ? (h.x === s.food.x && h.z === s.food.z)
        : (h.x === s.food.x && h.y === s.food.y);
      lane.scale.set(a.x ? this.N : 0.7, a.y ? this.N : 0.7, a.z ? this.N : 0.7);
      lane.position.set(a.x ? 0 : hx, a.y ? 0.5 : hy, a.z ? 0 : hz);
      lane.material.opacity = hitsFruit ? 0.55 : (isDir ? pulse * 2.2 : pulse);
      lane.material.color.setHex(hitsFruit ? 0xff2244 : (a.x ? 0x66b3ff : a.y ? 0x4d9fff : 0x3385ff));
    });

    const f = s.food;
    this.food.position.set(this._cell(f.x), this._cell(f.y) + 0.5, this._cell(f.z));
    this.foodLight.position.set(this._cell(f.x), this._cell(f.y) + 1.2, this._cell(f.z));
    const p = 1 + Math.sin(now * 0.005) * 0.15;
    this.food.scale.set(p, p, p);
    this.food.rotation.y += 0.003;
    const fx = this._cell(f.x), fy = this._cell(f.y) + 0.5, fz = this._cell(f.z);
    const fsf = 1 + (f.y - (this.N - 1) / 2 + this.OFF) / this.N * 0.5;
    this.foodBlob.position.x = fx;
    this.foodBlob.position.z = fz;
    this.foodBlob.scale.set(fsf, fsf, fsf);
    this.fruitLanes.forEach((fl) => {
      const a = fl.userData.axis;
      fl.scale.set(a.x ? this.N : 0.7, a.y ? this.N : 0.7, a.z ? this.N : 0.7);
      fl.position.set(a.x ? 0 : fx, a.y ? 0.5 : fy, a.z ? 0 : fz);
      fl.material.opacity = 0.13 + Math.sin(now * 0.004 + 1.3) * 0.05;
    });

    this.boxEdges.material.opacity = vm.torus ? 0.22 : 0.55;
    const sway = Math.sin(now * 0.0002) * 0.6;
    this.camera.position.set(this.N * 1.35 + sway, this.N * 1.5, this.N * 1.35 - sway);
    this.camera.lookAt(0, 0.5, 0);
    this.renderer.render(this.scene, this.camera);
  }
};
