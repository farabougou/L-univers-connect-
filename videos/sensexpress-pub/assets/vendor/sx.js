/* SensExpress — seek-safe effects. Every builder returns render(t): a pure function of frame-local time. */
(function () {
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const win = (t, a, d) => clamp((t - a) / d);
  const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);
  const inOut = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  function rng(s) { return () => { s |= 0; s = (s + 0x6d2b79f5) | 0; let r = Math.imul(s ^ (s >>> 15), 1 | s); r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r; return ((r ^ (r >>> 14)) >>> 0) / 4294967296; }; }

  // ── perfume mist: soft particles rising and swaying from an origin (2D canvas) ──
  function mist(canvas, o) {
    const ctx = canvas.getContext("2d"), r = rng(o.seed || 7), n = o.n || 46;
    const P = []; for (let i = 0; i < n; i++) P.push({ ph: r(), sp: 0.12 + r() * 0.16, dx: (r() - 0.5) * 2, sw: 0.6 + r() * 1.2, sz: 0.6 + r() * 0.8, gold: r() < (o.gold == null ? 0.25 : o.gold) });
    return function (t, k = 1) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (k <= 0.001) return;
      ctx.globalCompositeOperation = "lighter";
      for (const p of P) {
        const life = (t * p.sp + p.ph) % 1;
        const x = o.x + p.dx * (o.spread || 120) * Math.pow(life, 0.8) + Math.sin(t * p.sw + p.ph * 9) * 26 * life;
        const y = o.y - life * (o.rise || 700);
        const rad = (o.size || 60) * p.sz * (0.35 + life * 1.6);
        const a = (o.alpha || 0.09) * Math.sin(life * Math.PI) * k;
        const g = ctx.createRadialGradient(x, y, 0, x, y, rad);
        const c = p.gold ? "233,194,33" : "255,246,226";
        g.addColorStop(0, `rgba(${c},${a.toFixed(4)})`); g.addColorStop(1, `rgba(${c},0)`);
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, rad, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
    };
  }

  // ── 3D diffuser (illustrative product shot): glossy black tower, gold rings, studio reflections, rising mist ──
  function diffuser(canvas, o = {}) {
    const W = canvas.width, H = canvas.height;
    if (THREE.ColorManagement) THREE.ColorManagement.legacyMode = false;
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1); renderer.setSize(W, H, false);
    renderer.outputEncoding = THREE.sRGBEncoding; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
    const scene = new THREE.Scene();
    // studio environment: dark room with soft boxes, prefiltered for reflections
    const env = new THREE.Scene();
    env.add(new THREE.Mesh(new THREE.SphereGeometry(30, 32, 16), new THREE.MeshBasicMaterial({ color: 0x050505, side: THREE.BackSide })));
    const box = (w, h, x, y, z, c, ry = 0) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: c, side: THREE.DoubleSide })); m.position.set(x, y, z); m.lookAt(0, 2, 0); env.add(m); };
    box(10, 14, -12, 6, 8, 0xffffff); box(4, 18, 13, 4, 2, 0xfff4d6); box(16, 3, 0, 16, 0, 0xffffff); box(6, 10, 3, 3, -14, 0xe9c221);
    const pm = new THREE.PMREMGenerator(renderer); scene.environment = pm.fromScene(env, 0.035).texture;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x101010, 0.25));
    const key = new THREE.DirectionalLight(0xfff3e0, 1.1); key.position.set(-5, 8, 7); scene.add(key);
    const rim = new THREE.DirectionalLight(0xffe2a0, 0.9); rim.position.set(6, 4, -6); scene.add(rim);
    const camera = new THREE.PerspectiveCamera(26, W / H, 0.1, 100);
    const G = new THREE.Group(); scene.add(G);
    const prof = [[0, 0], [0.82, 0], [0.86, 0.05], [0.86, 0.26], [0.82, 0.31], [0.79, 1.6], [0.8, 2.9], [0.76, 3.3], [0.62, 3.6], [0.4, 3.78], [0.18, 3.86], [0, 3.88]].map(([x, y]) => new THREE.Vector2(x, y));
    const black = new THREE.MeshPhysicalMaterial({ color: 0x0b0b0b, roughness: 0.22, metalness: 0.15, clearcoat: 1, clearcoatRoughness: 0.08 });
    const gold = new THREE.MeshStandardMaterial({ color: 0xe9c221, metalness: 1, roughness: 0.22 });
    G.add(new THREE.Mesh(new THREE.LatheGeometry(prof, 128), black));
    const ring = (y, r, h) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 128, 1, true), gold); m.position.y = y; G.add(m); };
    ring(0.285, 0.832, 0.06); ring(3.1, 0.79, 0.035);
    const noz = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.13, 0.16, 48), gold); noz.position.y = 3.93; G.add(noz);
    const ped = new THREE.Mesh(new THREE.CylinderGeometry(2.3, 2.4, 0.16, 128), new THREE.MeshStandardMaterial({ color: 0x0d0d0d, roughness: 0.55, metalness: 0.0 }));
    ped.position.y = -0.08; scene.add(ped);
    const pedRing = new THREE.Mesh(new THREE.TorusGeometry(2.35, 0.012, 8, 160), new THREE.MeshBasicMaterial({ color: 0xe9c221 })); pedRing.rotation.x = Math.PI / 2; pedRing.position.y = 0.005; scene.add(pedRing);
    // mist sprites
    const c2 = document.createElement("canvas"); c2.width = c2.height = 128; const g2 = c2.getContext("2d");
    const gr = g2.createRadialGradient(64, 64, 0, 64, 64, 64); gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.4, "rgba(255,255,255,0.35)"); gr.addColorStop(1, "rgba(255,255,255,0)");
    g2.fillStyle = gr; g2.fillRect(0, 0, 128, 128); const tex = new THREE.CanvasTexture(c2);
    const r = rng(5), NM = 260, seeds = [], pos = new Float32Array(NM * 3), col = new Float32Array(NM * 3);
    for (let i = 0; i < NM; i++) seeds.push([r(), 0.18 + r() * 0.2, (r() - 0.5) * 2, (r() - 0.5) * 2, r() * 6]);
    const pg = new THREE.BufferGeometry(); pg.setAttribute("position", new THREE.BufferAttribute(pos, 3)); pg.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const pmat = new THREE.PointsMaterial({ size: 1.25, map: tex, transparent: true, opacity: 0.0, depthWrite: false, blending: THREE.AdditiveBlending, vertexColors: true });
    scene.add(new THREE.Points(pg, pmat));
    const T = Object.assign({ in: 0, mist: 0.4, push: [0, 4.5], pull: [4.6, 1.3] }, o);
    return function (t) {
      const life0 = t;
      for (let i = 0; i < NM; i++) {
        const [ph, sp, dx, dz, sw] = seeds[i]; const l = (life0 * sp + ph) % 1;
        pos[i * 3] = dx * 0.9 * l + Math.sin(t * 0.9 + sw) * 0.25 * l;
        pos[i * 3 + 1] = 4.02 + l * 2.4;
        pos[i * 3 + 2] = dz * 0.6 * l;
        const a = Math.sin(l * Math.PI) * Math.pow(1 - l, 1.5) * 0.11; col[i * 3] = a; col[i * 3 + 1] = a * 0.97; col[i * 3 + 2] = a * 0.9;
      }
      pg.attributes.position.needsUpdate = true; pg.attributes.color.needsUpdate = true;
      G.rotation.y = 0.6 + t * 0.32;
      const push = inOut(win(t, T.push[0], T.push[1])), pull = inOut(win(t, T.pull[0], T.pull[1]));
      pmat.opacity = 0.9 * ease(win(t, T.mist, 1.0)) * (1 - 0.8 * pull);
      const d = 17 - push * 4.5 + pull * (o.pullDist || 6.5);
      const a = -0.3 + t * 0.05;
      camera.position.set(Math.sin(a) * d, 2.6 + push * 0.6 + pull * 0.6, Math.cos(a) * d);
      camera.lookAt(0, 2.3 + push * 0.5 - pull * (o.pullLook || 0), 0);
      renderer.render(scene, camera);
    };
  }


  // ── gold dust: fine sparkles drifting slowly and twinkling (2D canvas) ──
  function dust(canvas, o = {}) {
    const ctx = canvas.getContext("2d"), r = rng(o.seed || 21), n = o.n || 90, W = canvas.width, H = canvas.height;
    const P = []; for (let i = 0; i < n; i++) P.push({ x: r() * W, y: r() * H, vy: 8 + r() * 26, vx: (r() - 0.5) * 10, s: 0.8 + r() * 2.4, ph: r() * 6.28, f: 0.6 + r() * 1.6 });
    return function (t, k = 1) {
      ctx.clearRect(0, 0, W, H); if (k <= 0.001) return;
      ctx.globalCompositeOperation = "lighter";
      for (const p of P) {
        const x = (p.x + p.vx * t + W) % W, y = ((p.y - p.vy * t) % H + H) % H;
        const a = (o.alpha || 0.7) * k * (0.35 + 0.65 * Math.pow(0.5 + 0.5 * Math.sin(t * p.f * 2 + p.ph), 3));
        const g = ctx.createRadialGradient(x, y, 0, x, y, p.s * 3);
        g.addColorStop(0, `rgba(255,236,170,${a.toFixed(3)})`); g.addColorStop(1, "rgba(233,194,33,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, p.s * 3, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
    };
  }
  window.SX = { mist, diffuser, dust, _: { clamp, win, ease, inOut, rng } };
})();
