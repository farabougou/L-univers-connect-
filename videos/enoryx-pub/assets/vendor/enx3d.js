/* Enoryx — 3D scene builders for the HyperFrames frames.
 * Each builder takes a <canvas> (1080×1920) and returns render(t) where t is the
 * frame-local time in seconds. Everything is a pure function of t (seeded data,
 * no clocks), so any seek renders the exact same image. Requires global THREE (r149).
 */
(function () {
  const W = 1080, H = 1920;
  const C = {
    navy: 0x050b1a, panel: 0x0c1730, line: 0x1e2a44, cyan: 0x38bdf8, ice: 0x7dd3fc,
    blue: 0x1d4ed8, orange: 0xea580c, green: 0x16a34a, white: 0xf8fafc, slate: 0x334155,
  };
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const ease = (x) => { x = clamp(x); return 1 - Math.pow(1 - x, 3); };          // power3.out
  const inOut = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  const back = (x, s = 1.7) => { x = clamp(x); const c3 = s + 1; return 1 + c3 * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2); };
  const win = (t, a, d) => clamp((t - a) / d);
  function rng(seed) { return function () { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let r = Math.imul(seed ^ (seed >>> 15), 1 | seed); r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r; return ((r ^ (r >>> 14)) >>> 0) / 4294967296; }; }

  if (THREE.ColorManagement) THREE.ColorManagement.legacyMode = false;
  function base(canvas, fov = 38) {
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1);
    renderer.setSize(W, H, false);
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.NoToneMapping;
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(C.navy, 0.035);
    const camera = new THREE.PerspectiveCamera(fov, W / H, 0.1, 200);
    scene.add(new THREE.HemisphereLight(0x9cc8ff, 0x0a1430, 0.75));
    const key = new THREE.DirectionalLight(0xdbe9ff, 1.2);
    key.position.set(6, 10, 8);
    scene.add(key);
    const v = new THREE.Vector3();
    const project = (p) => { v.copy(p).project(camera); return { x: (v.x + 1) / 2 * W, y: (1 - v.y) / 2 * H, z: v.z }; };
    return { renderer, scene, camera, project };
  }

  // soft additive glow sprite (no text → no font dependency)
  let glowTex = null;
  function glow(color, size) {
    if (!glowTex) {
      const c = document.createElement("canvas"); c.width = c.height = 128;
      const g = c.getContext("2d"); const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
      gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.25, "rgba(255,255,255,0.45)"); gr.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = gr; g.fillRect(0, 0, 128, 128); glowTex = new THREE.CanvasTexture(c);
    }
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false }));
    s.scale.set(size, size, 1); return s;
  }
  // HTML label pinned to a 3D point
  function pin(el, project, p, dx = 0, dy = 0) {
    if (!el) return; const q = project(p);
    el.style.transform = `translate(${(q.x + dx).toFixed(1)}px, ${(q.y + dy).toFixed(1)}px)`;
  }
  function grid(scene, size, div, y, color = C.line, op = 0.55) {
    const g = new THREE.GridHelper(size, div, color, color); g.position.y = y;
    g.material.transparent = true; g.material.opacity = op; scene.add(g); return g;
  }

  // ── 1 · night office building, heating still running ─────────────────────
  function building(canvas) {
    const { renderer, scene, camera } = base(canvas, 40);
    scene.fog.density = 0.03;
    grid(scene, 80, 40, 0, 0x13213f, 0.6);
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.MeshStandardMaterial({ color: 0x060d1f, roughness: 1 }));
    ground.rotation.x = -Math.PI / 2; ground.position.y = -0.01; scene.add(ground);
    const r = rng(7);
    // neighbours
    for (let i = 0; i < 14; i++) {
      const h = 2 + r() * 5, w = 1.6 + r() * 1.6;
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, w), new THREE.MeshStandardMaterial({ color: 0x07102a, roughness: 0.9 }));
      const a = Math.PI * (1.05 + r() * 0.9), d = 9 + r() * 10; m.position.set(Math.cos(a) * d, h / 2, Math.sin(a) * d - 4); scene.add(m);
    }
    const B = { w: 4.2, h: 9, d: 3.4 };
    const tower = new THREE.Mesh(new THREE.BoxGeometry(B.w, B.h, B.d), new THREE.MeshStandardMaterial({ color: 0x0d1a38, roughness: 0.55, metalness: 0.2 }));
    tower.position.y = B.h / 2; scene.add(tower);
    const roof = new THREE.Mesh(new THREE.BoxGeometry(B.w + 0.2, 0.25, B.d + 0.2), new THREE.MeshStandardMaterial({ color: 0x1e2a44 }));
    roof.position.y = B.h + 0.12; scene.add(roof);
    // windows on front (z+) and right (x+) faces
    const wins = [];
    const winGeo = new THREE.PlaneGeometry(0.52, 0.5);
    for (let f = 0; f < 2; f++) for (let row = 0; row < 11; row++) for (let col = 0; col < (f ? 4 : 5); col++) {
      const m = new THREE.Mesh(winGeo, new THREE.MeshBasicMaterial({ color: 0x0f1d3c }));
      const y = 0.9 + row * 0.74;
      if (f === 0) { m.position.set(-1.6 + col * 0.8, y, B.d / 2 + 0.01); }
      else { m.position.set(B.w / 2 + 0.01, y, -1.2 + col * 0.8); m.rotation.y = Math.PI / 2; }
      m.userData = { k: r(), warm: r() < 0.82 };
      scene.add(m); wins.push(m);
    }
    const warmA = new THREE.Color(0x3a1a0c), warmB = new THREE.Color(0xc2541c), cold = new THREE.Color(0x0f1d3c);
    const roomLight = new THREE.PointLight(0xea580c, 0, 14); roomLight.position.set(2.5, 5, 3); scene.add(roomLight);
    // heat plumes: seeded particles rising from the roof
    const N = 260, pos = new Float32Array(N * 3), seeds = [];
    for (let i = 0; i < N; i++) seeds.push([r() * B.w - B.w / 2, r() * B.d - B.d / 2, r(), 0.6 + r() * 0.8]);
    const pg = new THREE.BufferGeometry(); pg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const pm = new THREE.PointsMaterial({ color: 0xff7a2e, size: 0.16, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
    scene.add(new THREE.Points(pg, pm));
    const moon = new THREE.Mesh(new THREE.SphereGeometry(1.1, 32, 32), new THREE.MeshBasicMaterial({ color: 0xdbe7ff }));
    moon.position.set(-9, 17, -22); scene.add(moon);
    const mg = glow(0x9fc4ff, 9); mg.position.copy(moon.position); scene.add(mg);
    const rg = glow(0xea580c, 7); rg.position.set(0, B.h + 1.5, 0); scene.add(rg);
    return function (t) {
      const heat = ease(win(t, 0.7, 1.2));
      wins.forEach((m) => {
        const k = ease(win(t, 0.7 + m.userData.k * 0.9, 0.5));
        m.material.color.copy(cold).lerp(m.userData.warm ? (m.userData.k > 0.5 ? warmB : warmA) : cold, k);
      });
      roomLight.intensity = 2.2 * heat;
      for (let i = 0; i < N; i++) {
        const [x, z, ph, sp] = seeds[i]; const life = ((t * sp * 0.45) + ph) % 1;
        pos[i * 3] = x * (1 + life * 0.6) + Math.sin(life * 9 + ph * 20) * 0.25;
        pos[i * 3 + 1] = B.h + 0.3 + life * 5.5;
        pos[i * 3 + 2] = z * (1 + life * 0.6);
      }
      pg.attributes.position.needsUpdate = true;
      pm.opacity = 0.75 * heat * (1 - 0.55 * ease(win(t, 4.3, 0.8)));
      rg.material.opacity = 0.6 * heat;
      const a = 0.62 + t * 0.05, d = 18 - ease(win(t, 0, 6)) * 1.5;
      camera.position.set(Math.sin(a) * d, 5.2 + t * 0.12, Math.cos(a) * d);
      camera.lookAt(0, 5.6, 0);
      renderer.render(scene, camera);
    };
  }

  // ── 2 · décret tertiaire bars ────────────────────────────────────────────
  function bars(canvas, labels) {
    const { renderer, scene, camera, project } = base(canvas, 36);
    grid(scene, 30, 30, 0, 0x1e2a44, 0.5);
    const plate = new THREE.Mesh(new THREE.BoxGeometry(7.2, 0.2, 2.6), new THREE.MeshStandardMaterial({ color: 0x0c1730, roughness: 0.6 }));
    plate.position.y = -0.1; scene.add(plate);
    const H = [5, 3, 2.5, 2], cols = [C.slate, C.cyan, C.blue, 0x1e40af], at = [0.4, 1.95, 3.9, 4.2];
    const meshes = H.map((h, i) => {
      const m = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1, 1.2), new THREE.MeshStandardMaterial({ color: cols[i], roughness: 0.35, metalness: 0.15, emissive: cols[i], emissiveIntensity: i ? 0.35 : 0.05 }));
      m.position.x = -2.4 + i * 1.6; scene.add(m); return m;
    });
    const tops = H.map(() => new THREE.Vector3());
    const halo = glow(C.cyan, 6); halo.position.set(-0.8, 1.5, 0.7); scene.add(halo);
    return function (t) {
      meshes.forEach((m, i) => {
        const k = ease(win(t, at[i], 0.8)); const h = Math.max(0.001, H[i] * k);
        m.scale.y = h; m.position.y = h / 2;
        tops[i].set(m.position.x, h + 0.15, 0.8);
      });
      halo.material.opacity = 0.7 * ease(win(t, 1.95, 0.8));
      const a = -0.28 + t * 0.07;
      camera.position.set(Math.sin(a) * 19, 6.5 - t * 0.25, Math.cos(a) * 19);
      camera.lookAt(0, 2.2, 0);
      renderer.render(scene, camera);
      labels.forEach((el, i) => { pin(el.v, project, tops[i], 0, -14); pin(el.y, project, new THREE.Vector3(meshes[i].position.x, -0.1, 1.1), 0, 26); });
    };
  }

  // ── orbital mark (shared by 3 and 6) ─────────────────────────────────────
  function mark(scale = 1) {
    const g = new THREE.Group();
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.62 * scale, 48, 48), new THREE.MeshStandardMaterial({ color: 0x7dd3fc, emissive: 0x1d4ed8, emissiveIntensity: 0.9, roughness: 0.25, metalness: 0.2 }));
    g.add(core);
    const cg = glow(C.ice, 4.2 * scale); g.add(cg);
    const rings = [];
    for (let i = 0; i < 3; i++) {
      const pivot = new THREE.Group(); pivot.rotation.z = i * Math.PI / 3;
      const ring = new THREE.Mesh(new THREE.TorusGeometry(2.3 * scale, 0.055 * scale, 16, 160), new THREE.MeshStandardMaterial({ color: 0x67e8f9, emissive: 0x2563eb, emissiveIntensity: 1.1, roughness: 0.3 }));
      ring.scale.y = 0.45; pivot.add(ring);
      const sat = new THREE.Mesh(new THREE.SphereGeometry(0.17 * scale, 24, 24), new THREE.MeshBasicMaterial({ color: 0xbae6fd }));
      const sg = glow(C.cyan, 1.1 * scale); sat.add(sg);
      pivot.add(sat); g.add(pivot); rings.push({ pivot, ring, sat });
    }
    return { g, core, cg, rings, scale };
  }
  function animMark(M, t, born) {
    const s = M.scale;
    M.core.scale.setScalar(Math.max(0.001, back(win(t, born + 0.15, 0.5), 2.2)));
    M.cg.material.opacity = 0.8 * ease(win(t, born + 0.2, 0.6));
    M.rings.forEach((R, i) => {
      const k = ease(win(t, born + i * 0.08, 0.8));
      R.ring.scale.set(0.3 + 0.7 * k, (0.3 + 0.7 * k) * 0.45, 1); R.ring.material.opacity = k; R.ring.material.transparent = true;
      const a = t * (0.9 + i * 0.25) + i * 2.1;
      R.sat.position.set(Math.cos(a) * 2.3 * s * R.ring.scale.x, Math.sin(a) * 2.3 * s * R.ring.scale.y, 0);
      R.sat.visible = t > born + 0.4;
      R.pivot.rotation.x = Math.sin(t * 0.5 + i) * 0.25;
    });
    M.g.rotation.y = t * 0.35;
  }

  // ── 3 · Enoryx connects equipment ────────────────────────────────────────
  function hub(canvas, labels, o = {}) {
    const AT = o.at || [0.95, 1.07, 1.19, 1.31], PULSE = o.pulse || 2.25, DUR = o.dur || 4.4;
    const { renderer, scene, camera, project } = base(canvas, 40);
    scene.fog.density = 0.02;
    grid(scene, 40, 40, -4.2, 0x13213f, 0.5);
    const M = mark(1); scene.add(M.g);
    const nodesP = [[-2.5, 3.0, 0.6], [2.5, 3.0, -0.4], [-2.5, -2.9, -0.6], [2.5, -2.9, 0.6]].map((a) => new THREE.Vector3(...a));
    const nodes = nodesP.map((p, i) => {
      const m = new THREE.Mesh(new THREE.BoxGeometry(1.5, 1.0, 1.0), new THREE.MeshStandardMaterial({ color: C.panel, emissive: 0x0b2a55, emissiveIntensity: 0.6, roughness: 0.4, metalness: 0.3 }));
      m.position.copy(p); scene.add(m);
      const led = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 16), new THREE.MeshBasicMaterial({ color: C.green })); led.position.set(0.55, 0.3, 0.51); m.add(led);
      return m;
    });
    const lines = nodesP.map((p) => {
      const geo = new THREE.BufferGeometry().setFromPoints([p, new THREE.Vector3(0, 0, 0)]);
      const l = new THREE.Line(geo, new THREE.LineDashedMaterial({ color: C.cyan, dashSize: 0.22, gapSize: 0.16, transparent: true, opacity: 0 }));
      l.computeLineDistances(); scene.add(l); return l;
    });
    const pulses = nodesP.map(() => { const s = glow(C.ice, 0.9); scene.add(s); return s; });
    return function (t) {
      animMark(M, t, 0);
      nodes.forEach((m, i) => {
        const k = back(win(t, AT[i], 0.5), 1.6);
        m.scale.setScalar(Math.max(0.001, k)); m.rotation.y = 0.4 * Math.sin(t * 0.8 + i);
        lines[i].material.opacity = 0.75 * ease(win(t, AT[i] + 0.2, 0.4));
        const ph = ((t - Math.max(PULSE, AT[i] + 0.5) - i * 0.15) / 0.8); const on = ph > 0 && ph < 6;
        const f = on ? ph % 1 : 0; pulses[i].position.copy(nodesP[i]).lerp(new THREE.Vector3(), f * f);
        pulses[i].material.opacity = on ? Math.sin(f * Math.PI) : 0;
      });
      const a = -0.35 + t * (0.53 / DUR), d = 21 - ease(win(t, 0, DUR)) * 1.5;
      camera.position.set(Math.sin(a) * d, 1.2 + t * 0.15, Math.cos(a) * d);
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
      labels.forEach((el, i) => pin(el, project, nodesP[i], 0, -78));
    };
  }

  // ── 4 & 5 · consumption curve in 3D ──────────────────────────────────────
  const NPT = 40;
  function refY(i) { return 2.2 + 1.3 * Math.sin(i / (NPT - 1) * Math.PI * 1.15); }
  function spike(i) { return i >= 20 && i <= 33 ? Math.sin((i - 20) / 13 * Math.PI) * 2.6 : 0; }
  const X = (i) => -4.2 + i * (8.4 / (NPT - 1));
  function tubeOf(ys, from, to, r = 0.09) {
    const pts = []; for (let i = from; i <= to; i++) pts.push(new THREE.Vector3(X(i), ys[i], 0));
    return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), Math.max(8, (to - from) * 6), r, 10, false);
  }
  function chartBase(scene) {
    grid(scene, 12, 12, 0, 0x1e2a44, 0.6);
    const back = new THREE.GridHelper(10, 10, 0x16264a, 0x16264a); back.rotation.x = Math.PI / 2; back.position.set(0, 3.5, -2); back.material.transparent = true; back.material.opacity = 0.35; scene.add(back);
    const refPts = []; for (let i = 0; i < NPT; i++) refPts.push(new THREE.Vector3(X(i), refY(i), 0));
    const ref = new THREE.Line(new THREE.BufferGeometry().setFromPoints(new THREE.CatmullRomCurve3(refPts).getPoints(200)), new THREE.LineDashedMaterial({ color: C.cyan, dashSize: 0.28, gapSize: 0.18, transparent: true, opacity: 0 }));
    ref.computeLineDistances(); scene.add(ref);
    return ref;
  }
  function detect(canvas, pins, o = {}) {
    const T = Object.assign({ ref: 0.25, ok: 1.05, bad: 2.05, wall: 2.6, peak: 2.75 }, o);
    const { renderer, scene, camera, project } = base(canvas, 36);
    scene.fog.density = 0.02;
    const ref = chartBase(scene);
    const real = []; const r = rng(3);
    for (let i = 0; i < NPT; i++) real.push(refY(i) + (r() - 0.5) * 0.18 + spike(i));
    const okMesh = new THREE.Mesh(tubeOf(real, 0, 20), new THREE.MeshStandardMaterial({ color: C.white, emissive: 0x334155, emissiveIntensity: 0.5, roughness: 0.3 }));
    const badMesh = new THREE.Mesh(tubeOf(real, 20, NPT - 1, 0.11), new THREE.MeshStandardMaterial({ color: C.orange, emissive: C.orange, emissiveIntensity: 0.8, roughness: 0.3 }));
    scene.add(okMesh); scene.add(badMesh);
    // translucent wall between reference and spike
    const wall = new THREE.BufferGeometry(); const wv = [];
    for (let i = 20; i < 33; i++) { const a = [X(i), refY(i)], b = [X(i + 1), refY(i + 1)], c = [X(i + 1), real[i + 1]], d = [X(i), real[i]];
      wv.push(a[0], a[1], 0, b[0], b[1], 0, c[0], c[1], 0, a[0], a[1], 0, c[0], c[1], 0, d[0], d[1], 0); }
    wall.setAttribute("position", new THREE.Float32BufferAttribute(wv, 3));
    const wm = new THREE.Mesh(wall, new THREE.MeshBasicMaterial({ color: C.orange, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false }));
    scene.add(wm);
    const peak = new THREE.Vector3(X(26), real[26], 0);
    const pg = glow(C.orange, 2.4); pg.position.copy(peak); scene.add(pg);
    const okCount = okMesh.geometry.index.count, badCount = badMesh.geometry.index.count;
    return function (t) {
      ref.material.opacity = 0.9 * ease(win(t, T.ref, 0.6));
      okMesh.geometry.setDrawRange(0, Math.floor(okCount * inOut(win(t, T.ok, 0.9)) / 3) * 3);
      badMesh.geometry.setDrawRange(0, Math.floor(badCount * inOut(win(t, T.bad, 0.8)) / 3) * 3);
      wm.material.opacity = 0.28 * ease(win(t, T.wall, 0.5));
      pg.material.opacity = 0.9 * ease(win(t, T.peak, 0.4)) * (0.8 + 0.2 * Math.sin(t * 8));
      const a = 0.35 - t * 0.07;
      camera.position.set(Math.sin(a) * 25, 4.2 + t * 0.1, Math.cos(a) * 25);
      camera.lookAt(0, 3.0, 0);
      renderer.render(scene, camera);
      pin(pins[0], project, peak, -150, -40);
      pin(pins[1], project, new THREE.Vector3(X(31), real[31], 0), -170, 30);
    };
  }
  function recover(canvas, o = {}) {
    const T = Object.assign({ k: 2.3, c: 2.9 }, o);
    const { renderer, scene, camera } = base(canvas, 36);
    scene.fog.density = 0.02;
    const ref = chartBase(scene); ref.material.opacity = 0.9;
    const hi = []; for (let i = 0; i < NPT; i++) hi.push(refY(i) + 2.0 * clamp((i - 3) / 8));
    const mat = new THREE.MeshStandardMaterial({ color: C.orange, emissive: C.orange, emissiveIntensity: 0.7, roughness: 0.3 });
    const mesh = new THREE.Mesh(tubeOf(hi, 0, NPT - 1, 0.11), mat); scene.add(mesh);
    const cO = new THREE.Color(C.orange), cG = new THREE.Color(C.green);
    const g = glow(C.green, 5); g.position.set(0, 3.3, 0.3); scene.add(g);
    let lastK = -1;
    return function (t) {
      const k = Math.round(inOut(win(t, T.k, 1.3)) * 60) / 60;
      if (k !== lastK) { const ys = hi.map((y, i) => y + (refY(i) - y) * k); mesh.geometry.dispose(); mesh.geometry = tubeOf(ys, 0, NPT - 1, 0.11); lastK = k; }
      const c = ease(win(t, T.c, 0.6)); mat.color.copy(cO).lerp(cG, c); mat.emissive.copy(cO).lerp(cG, c);
      g.material.opacity = 0.55 * c;
      const a = -0.3 + t * 0.06;
      camera.position.set(Math.sin(a) * 25, 5 - t * 0.1, Math.cos(a) * 25);
      camera.lookAt(0, 4.6, 0);
      renderer.render(scene, camera);
    };
  }

  // ── 6 · signature ────────────────────────────────────────────────────────
  function signature(canvas) {
    const { renderer, scene, camera } = base(canvas, 40);
    scene.fog.density = 0.015;
    const M = mark(0.9); M.g.position.y = 0; scene.add(M.g);
    const r = rng(11); const N = 400, pos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) { const a = r() * Math.PI * 2, d = 5 + r() * 14; pos[i * 3] = Math.cos(a) * d; pos[i * 3 + 1] = (r() - 0.5) * 30; pos[i * 3 + 2] = Math.sin(a) * d - 6; }
    const pg = new THREE.BufferGeometry(); pg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const pts = new THREE.Points(pg, new THREE.PointsMaterial({ color: 0x7dd3fc, size: 0.07, transparent: true, opacity: 0.6, depthWrite: false }));
    scene.add(pts);
    return function (t) {
      animMark(M, t, 0);
      pts.rotation.y = t * 0.05;
      const d = 19.5 - ease(win(t, 0, 3)) * 2.5;
      camera.position.set(Math.sin(0.25 - t * 0.06) * d, -2.2 + t * 0.05, Math.cos(0.25 - t * 0.06) * d);
      camera.lookAt(0, -2.6, 0);
      renderer.render(scene, camera);
    };
  }

  window.ENX3D = { building, bars, hub, detect, recover, signature, _: { C, clamp, ease, inOut, back, win, rng, base, glow, pin, grid, mark, animMark } };
})();
