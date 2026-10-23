/* SK Print — 3D scene builders. builder(canvas, …) → render(t), pure function of t (seeded, no clocks).
 * 3D lettering is extruded from the Helvetiker Bold typeface (font-bold.js), parsed here without FontLoader. */
(function () {
  const W = 1080, H = 1920;
  const SK = { red: 0xe00511, navy: 0x2e2e8e, orange: 0xf58f20, c: 0x00a0e3, m: 0xe5007d, y: 0xffde00, k: 0x1d1d1b, white: 0xf7f7fa };
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const win = (t, a, d) => clamp((t - a) / d);
  const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);
  const inOut = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  const back = (x, s = 1.7) => { x = clamp(x); const c = s + 1; return 1 + c * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2); };
  const lerp = (a, b, k) => a + (b - a) * k;
  function rng(s) { return () => { s |= 0; s = (s + 0x6d2b79f5) | 0; let r = Math.imul(s ^ (s >>> 15), 1 | s); r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r; return ((r ^ (r >>> 14)) >>> 0) / 4294967296; }; }
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const std = (color, o = {}) => new THREE.MeshStandardMaterial(Object.assign({ color, roughness: 0.38, metalness: 0.05 }, o));

  function base(canvas, fov = 38, bg = null) {
    if (THREE.ColorManagement) THREE.ColorManagement.legacyMode = false;
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1); renderer.setSize(W, H, false); renderer.outputEncoding = THREE.sRGBEncoding;
    const scene = new THREE.Scene(); if (bg !== null) scene.background = new THREE.Color(bg);
    const camera = new THREE.PerspectiveCamera(fov, W / H, 0.1, 200);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x404060, 1.0));
    const key = new THREE.DirectionalLight(0xffffff, 1.3); key.position.set(5, 9, 8); scene.add(key);
    const rim = new THREE.DirectionalLight(0xffd6a8, 0.6); rim.position.set(-6, 3, -4); scene.add(rim);
    const v = V(0, 0, 0);
    const project = (p) => { v.copy(p).project(camera); return { x: (v.x + 1) / 2 * W, y: (1 - v.y) / 2 * H }; };
    return { renderer, scene, camera, project };
  }
  let glowTex = null;
  function glow(color, size) {
    if (!glowTex) { const c = document.createElement("canvas"); c.width = c.height = 128; const g = c.getContext("2d"); const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
      gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.3, "rgba(255,255,255,0.4)"); gr.addColorStop(1, "rgba(255,255,255,0)"); g.fillStyle = gr; g.fillRect(0, 0, 128, 128); glowTex = new THREE.CanvasTexture(c); }
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false })); s.scale.set(size, size, 1); return s;
  }
  function pin(el, project, p, dx = 0, dy = 0) { if (!el) return; const q = project(p); el.style.transform = `translate(${(q.x + dx).toFixed(1)}px, ${(q.y + dy).toFixed(1)}px)`; }

  // ── typeface → extruded 3D text ──────────────────────────────────────────
  function glyphShapes(ch, size) {
    const f = window.SK_FONT, g = f.glyphs[ch] || f.glyphs["?"], s = size / f.resolution;
    const path = new THREE.ShapePath();
    if (g.o) {
      const o = g._cached || (g._cached = g.o.split(" "));
      for (let i = 0; i < o.length;) {
        const a = o[i++];
        if (a === "m") path.moveTo(o[i++] * s, o[i++] * s);
        else if (a === "l") path.lineTo(o[i++] * s, o[i++] * s);
        else if (a === "q") { const x = o[i++] * s, y = o[i++] * s, cx = o[i++] * s, cy = o[i++] * s; path.quadraticCurveTo(cx, cy, x, y); }
        else if (a === "b") { const x = o[i++] * s, y = o[i++] * s, c1x = o[i++] * s, c1y = o[i++] * s, c2x = o[i++] * s, c2y = o[i++] * s; path.bezierCurveTo(c1x, c1y, c2x, c2y, x, y); }
      }
    }
    return { shapes: path.toShapes(), adv: g.ha * s };
  }
  function text3d(str, size, depth, mats) {
    const grp = new THREE.Group(); let x = 0; const letters = [];
    [...str].forEach((ch, i) => {
      const { shapes, adv } = glyphShapes(ch, size);
      if (shapes.length) {
        const geo = new THREE.ExtrudeGeometry(shapes, { depth, bevelEnabled: true, bevelThickness: size * 0.03, bevelSize: size * 0.02, bevelSegments: 3, curveSegments: 8 });
        geo.computeBoundingBox(); const bb = geo.boundingBox; const cx = (bb.max.x + bb.min.x) / 2, cy = (bb.max.y + bb.min.y) / 2;
        geo.translate(-cx, -cy, -depth / 2);
        const m = new THREE.Mesh(geo, Array.isArray(mats) ? mats[i % mats.length] : mats);
        const holder = new THREE.Group(); holder.position.x = x + cx; holder.userData.cy = cy; holder.add(m); grp.add(holder); letters.push(holder);
      }
      x += adv;
    });
    letters.forEach((l) => { l.position.x -= x / 2; l.position.y = l.userData.cy - size * 0.36; });
    grp.userData.letters = letters; grp.userData.width = x; return grp;
  }
  // SK Print lockup: big S (navy) + K (red), "PRINT" underneath, CMYK swoosh
  function logo(scale = 1) {
    const g = new THREE.Group();
    const sk = text3d("SK", 3.2 * scale, 0.9 * scale, [std(SK.navy, { roughness: 0.3 }), std(SK.red, { roughness: 0.3 })]);
    sk.position.y = 0.7 * scale; g.add(sk);
    const pr = text3d("Print", 1.05 * scale, 0.35 * scale, std(SK.navy, { roughness: 0.35 }));
    pr.position.set(1.0 * scale, -1.55 * scale, 0.2 * scale); g.add(pr);
    const sw = [SK.c, SK.m, SK.y, SK.k].map((c, i) => {
      const pts = []; for (let k = 0; k <= 40; k++) { const u = k / 40; pts.push(V(lerp(-2.9, 2.9, u) * scale, (-2.9 + 0.7 * Math.sin(u * Math.PI) - i * 0.16) * scale, (0.8 + 0.3 * Math.sin(u * 6)) * scale)); }
      const m = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 80, 0.07 * scale, 8, false), new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 0.25, roughness: 0.3 }));
      g.add(m); return m;
    });
    g.userData = { sk, pr, sw };
    return g;
  }
  function animLogo(L, t, t0) {
    const [S, Kk] = L.userData.sk.userData.letters;
    const a = ease(win(t, t0, 0.7)), b = ease(win(t, t0 + 0.12, 0.7));
    S.position.z = (1 - a) * 6; S.rotation.y = (1 - a) * -2.4; S.scale.setScalar(Math.max(0.001, a));
    Kk.position.z = (1 - b) * 6; Kk.rotation.y = (1 - b) * 2.4; Kk.scale.setScalar(Math.max(0.001, b));
    const p = ease(win(t, t0 + 0.55, 0.5)); L.userData.pr.scale.setScalar(Math.max(0.001, p)); L.userData.pr.position.x = lerp(3, 1.0, p);
    L.userData.sw.forEach((m, i) => { const cnt = m.geometry.index.count; m.geometry.setDrawRange(0, Math.floor(cnt * inOut(win(t, t0 + 0.7 + i * 0.07, 0.6)) / 3) * 3); });
  }

  // canvas textures (shapes and colour only — no text, no fonts needed)
  function tex(w, h, draw) { const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h); const t = new THREE.CanvasTexture(c); t.encoding = THREE.sRGBEncoding; return t; }
  const css = (n) => "#" + n.toString(16).padStart(6, "0");
  function printDesign(g, w, h, seed, bg) {
    const r = rng(seed); g.fillStyle = bg; g.fillRect(0, 0, w, h);
    const cols = [SK.red, SK.navy, SK.orange, SK.c, SK.m, SK.y].map(css);
    for (let i = 0; i < 7; i++) { g.fillStyle = cols[Math.floor(r() * cols.length)]; g.globalAlpha = 0.85; g.beginPath(); g.arc(r() * w, r() * h, (0.12 + r() * 0.3) * Math.min(w, h), 0, Math.PI * 2); g.fill(); }
    g.globalAlpha = 1; g.fillStyle = "#ffffff"; g.fillRect(w * 0.08, h * 0.7, w * 0.6, h * 0.06); g.fillRect(w * 0.08, h * 0.8, w * 0.4, h * 0.04);
  }

  // ── 1 · the idea: a light bulb switches on, CMYK sparks burst out ─────────
  function idea(canvas) {
    const { renderer, scene, camera } = base(canvas, 36);
    const bulb = new THREE.Group(); scene.add(bulb);
    const glass = new THREE.Mesh(new THREE.SphereGeometry(1.6, 48, 48), new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: 0.18, roughness: 0.05, metalness: 0.0 }));
    glass.position.y = 0.6; bulb.add(glass);
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.8, 1.05, 1.0, 32), new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: 0.18 })); neck.position.y = -1.0; bulb.add(neck);
    for (let i = 0; i < 4; i++) { const r = new THREE.Mesh(new THREE.TorusGeometry(0.78 - i * 0.02, 0.09, 12, 40), std(0xb9bec7, { metalness: 0.85, roughness: 0.25 })); r.rotation.x = Math.PI / 2; r.position.y = -1.6 - i * 0.2; bulb.add(r); }
    const tip = new THREE.Mesh(new THREE.SphereGeometry(0.3, 16, 16), std(0x2b2b2b)); tip.position.y = -2.45; bulb.add(tip);
    const filM = new THREE.MeshStandardMaterial({ color: 0xffd28a, emissive: 0xffb347, emissiveIntensity: 0 });
    const fil = new THREE.Mesh(new THREE.TorusKnotGeometry(0.35, 0.03, 80, 8, 2, 5), filM); fil.position.y = 0.4; bulb.add(fil);
    const halo = glow(0xffd28a, 9); halo.position.y = 0.6; bulb.add(halo);
    const light = new THREE.PointLight(0xffd28a, 0, 20); light.position.y = 0.6; bulb.add(light);
    // sparks
    const r = rng(5), N = 160, pos = new Float32Array(N * 3), col = new Float32Array(N * 3), dirs = [];
    const cl = [SK.c, SK.m, SK.y, SK.red, SK.orange].map((c) => new THREE.Color(c));
    for (let i = 0; i < N; i++) { const th = r() * Math.PI * 2, ph = Math.acos(2 * r() - 1); dirs.push([Math.sin(ph) * Math.cos(th), Math.cos(ph), Math.sin(ph) * Math.sin(th), 2 + r() * 4]); const c = cl[i % cl.length]; col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b; }
    const pg = new THREE.BufferGeometry(); pg.setAttribute("position", new THREE.BufferAttribute(pos, 3)); pg.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const pm = new THREE.PointsMaterial({ size: 0.28, vertexColors: true, map: glow(0xffffff, 1).material.map, transparent: true, depthWrite: false }); scene.add(new THREE.Points(pg, pm));
    return function (t) {
      const on = t < 0.35 ? 0 : t < 0.55 ? (Math.sin(t * 90) > 0 ? 1 : 0.2) : 1;
      filM.emissiveIntensity = 2.2 * on; halo.material.opacity = 0.85 * on; light.intensity = 2.5 * on;
      glass.material.opacity = 0.18 + 0.2 * on;
      const b = ease(win(t, 0.9, 1.1));
      dirs.forEach(([x, y, z, sp], i) => { const d = b * sp; pos[i * 3] = x * d; pos[i * 3 + 1] = 0.6 + y * d; pos[i * 3 + 2] = z * d; });
      pg.attributes.position.needsUpdate = true; pm.opacity = b > 0 ? 1 - 0.6 * win(t, 1.6, 0.5) : 0;
      bulb.rotation.y = t * 0.4; bulb.position.y = 0.2 + Math.sin(t * 2) * 0.06;
      camera.position.set(0, 0.2, 13 - ease(win(t, 0, 2.1)) * 2.5); camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
    };
  }

  // ── 2 · logo lockup ───────────────────────────────────────────────────────
  function logoScene(canvas, o = {}) {
    const { renderer, scene, camera } = base(canvas, 34);
    const L = logo(1); L.position.y = o.y || 1.6; scene.add(L);
    const sh = glow(0x2e2e8e, 9); sh.material.blending = THREE.NormalBlending; sh.material.opacity = 0.18; sh.position.set(0, (o.y || 1.6) - 3.2, -1); scene.add(sh);
    return function (t) {
      animLogo(L, t, o.t0 || 0);
      L.rotation.y = Math.sin(t * 0.8) * 0.18; L.rotation.x = Math.sin(t * 0.6) * 0.05;
      camera.position.set(0, 0.4, o.z || 25); camera.lookAt(0, o.look || 0.6, 0);
      renderer.render(scene, camera);
    };
  }

  // ── 3 · textile: heat press prints a T-shirt, then a cap and a jersey ─────
  function tshirtShape(w = 3.2, h = 3.8) {
    const s = new THREE.Shape(), x = w / 2, y = h / 2;
    s.moveTo(-0.45, y); s.quadraticCurveTo(0, y - 0.45, 0.45, y);       // collar
    s.lineTo(x, y - 0.15); s.lineTo(x + 0.95, y - 1.0); s.lineTo(x + 0.45, y - 1.55); s.lineTo(x - 0.05, y - 1.15);
    s.lineTo(x - 0.05, -y); s.lineTo(-x + 0.05, -y); s.lineTo(-x + 0.05, y - 1.15);
    s.lineTo(-x - 0.45, y - 1.55); s.lineTo(-x - 0.95, y - 1.0); s.lineTo(-x, y - 0.15); s.lineTo(-0.45, y);
    return s;
  }
  function textile(canvas, pins, o) {
    const { renderer, scene, camera, project } = base(canvas, 38);
    const geo = new THREE.ExtrudeGeometry(tshirtShape(), { depth: 0.25, bevelEnabled: true, bevelThickness: 0.08, bevelSize: 0.08, bevelSegments: 4 }); geo.translate(0, 0, -0.125);
    const shirt = new THREE.Group(); shirt.add(new THREE.Mesh(geo, std(0xffffff, { roughness: 0.8 }))); scene.add(shirt);
    const decalT = tex(512, 512, (g, w, h) => { printDesign(g, w, h, 3, "rgba(0,0,0,0)"); g.clearRect(0, 0, w, h);
      g.fillStyle = css(SK.red); g.beginPath(); g.arc(w * 0.5, h * 0.42, w * 0.32, 0, Math.PI * 2); g.fill();
      g.fillStyle = css(SK.navy); g.beginPath(); g.arc(w * 0.38, h * 0.36, w * 0.18, 0, Math.PI * 2); g.fill();
      [[SK.c, 0.2], [SK.m, 0.32], [SK.y, 0.44], [SK.orange, 0.56]].forEach(([c, x]) => { g.fillStyle = css(c); g.fillRect(w * x, h * 0.78, w * 0.1, h * 0.08); }); });
    const decal = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 2.2), new THREE.MeshStandardMaterial({ map: decalT, transparent: true, opacity: 0, roughness: 0.7 }));
    decal.position.set(0, 0.2, 0.22); shirt.add(decal);
    // heat press
    const press = new THREE.Group(); scene.add(press);
    const plate = new THREE.Mesh(new THREE.BoxGeometry(3.6, 0.35, 3.0), std(0x2b2b2e, { metalness: 0.7, roughness: 0.3 })); press.add(plate);
    const hot = new THREE.Mesh(new THREE.BoxGeometry(3.4, 0.05, 2.8), new THREE.MeshStandardMaterial({ color: 0xff5a1f, emissive: 0xff5a1f, emissiveIntensity: 0.6 })); hot.position.y = -0.2; press.add(hot);
    const arm = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.3, 3.5), std(SK.red, { metalness: 0.3 })); arm.position.set(0, 0.35, -0.6); press.add(arm);
    // cap + jersey
    const cap = new THREE.Group(); const dome = new THREE.Mesh(new THREE.SphereGeometry(1.0, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), std(SK.navy, { roughness: 0.7 })); cap.add(dome);
    const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 0.9, 0.06, 32, 1, false, -Math.PI / 2, Math.PI), std(SK.navy)); brim.scale.set(1, 1, 1.2); brim.position.set(0, 0.02, 0.55); cap.add(brim);
    const capLogo = new THREE.Mesh(new THREE.CircleGeometry(0.28, 24), new THREE.MeshStandardMaterial({ color: SK.red })); capLogo.position.set(0, 0.55, 0.85); capLogo.rotation.x = -0.6; cap.add(capLogo);
    cap.position.set(-2.0, -3.6, 1.0); scene.add(cap);
    const jersey = new THREE.Group(); jersey.add(new THREE.Mesh(geo, std(SK.navy, { roughness: 0.7 })));
    const num = text3d("10", 1.5, 0.12, std(0xffffff)); num.position.set(0, 0.1, 0.25); jersey.add(num);
    const stripe = new THREE.Mesh(new THREE.BoxGeometry(0.35, 3.6, 0.05), std(SK.orange)); stripe.position.set(1.15, -0.1, 0.22); jersey.add(stripe);
    jersey.scale.setScalar(0.62); jersey.position.set(2.0, -3.5, 1.0); scene.add(jersey);
    const puff = glow(0xffffff, 5); scene.add(puff);
    return function (t) {
      const down = inOut(win(t, o.press, 0.35)) * (1 - inOut(win(t, o.press + 0.7, 0.35)));
      press.position.set(0, lerp(9, 0.55, down), 0.1);
      press.rotation.x = lerp(-0.5, 0, down);
      decal.material.opacity = ease(win(t, o.press + 0.65, 0.3));
      puff.position.set(0, 0.6, 0.6); puff.material.opacity = 0.7 * Math.sin(Math.PI * win(t, o.press + 0.4, 0.8));
      shirt.position.y = 0.9; shirt.rotation.y = Math.sin(t * 0.7) * 0.25 + (1 - ease(win(t, 0, 0.6))) * 1.2;
      const kc = back(win(t, o.cap, 0.5), 1.7), kj = back(win(t, o.jersey, 0.5), 1.7);
      cap.scale.setScalar(Math.max(0.001, kc)); cap.rotation.y = t * 0.9; cap.rotation.x = 0.35;
      jersey.scale.setScalar(Math.max(0.001, 0.62 * kj)); jersey.rotation.y = -0.4 + Math.sin(t) * 0.2;
      camera.position.set(Math.sin(t * 0.15) * 1.0, 0.6, 18); camera.lookAt(0, -0.2, 0);
      renderer.render(scene, camera);
      pin(pins[0], project, V(0, 3.4, 0)); pin(pins[1], project, V(2.0, -1.9, 1.0)); pin(pins[2], project, V(-2.0, -2.3, 1.0));
    };
  }

  // ── 4 · paper: a printer ejects business cards, flyers, posters, banners, stickers ──
  function paper(canvas, pins, at) {
    const { renderer, scene, camera, project } = base(canvas, 38);
    const pr = new THREE.Group(); scene.add(pr); pr.position.set(0, -3.8, 0);
    const body = new THREE.Mesh(new THREE.BoxGeometry(5.2, 1.8, 3.0), std(0xeef0f4, { roughness: 0.4 })); pr.add(body);
    const top = new THREE.Mesh(new THREE.BoxGeometry(5.2, 0.25, 3.0), std(0x2b2b2e)); top.position.y = 1.0; pr.add(top);
    const slot = new THREE.Mesh(new THREE.BoxGeometry(4.0, 0.12, 0.2), std(0x111111)); slot.position.set(0, 0.2, 1.52); pr.add(slot);
    [SK.c, SK.m, SK.y, SK.k].forEach((c, i) => { const ink = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.5, 0.1), std(c)); ink.position.set(1.4 + i * 0.45 - 0.7, -0.3, 1.52); pr.add(ink); });
    const items = [
      { w: 1.8, h: 1.05, to: V(-1.9, 3.3, 0.5), rz: -0.25, seed: 1, bg: "#ffffff" },   // business card
      { w: 1.8, h: 2.5, to: V(2.0, 2.6, 0.2), rz: 0.18, seed: 2, bg: "#fff6ea" },      // flyer
      { w: 2.6, h: 3.6, to: V(-1.6, -0.1, -0.6), rz: 0.08, seed: 3, bg: "#ffffff" },   // poster
      { w: 4.0, h: 1.3, to: V(1.0, 0.4, 0.6), rz: -0.06, seed: 4, bg: "#2e2e8e" },     // banner
      { w: 1.3, h: 1.3, to: V(2.1, -1.4, 1.0), rz: 0.3, seed: 5, bg: "#f58f20", round: true }, // sticker
    ].map((it) => {
      const t = tex(512, Math.round(512 * it.h / it.w), (g, w, h) => printDesign(g, w, h, it.seed, it.bg));
      const geo = it.round ? new THREE.CircleGeometry(it.w / 2, 48) : new THREE.PlaneGeometry(it.w, it.h);
      const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: t, side: THREE.DoubleSide, roughness: 0.55 }));
      scene.add(m); it.m = m; return it;
    });
    const from = V(0, -3.6, 1.6);
    return function (t) {
      pr.position.y = -3.8 + Math.sin(t * 30) * 0.01 * (t < 3.2 ? 1 : 0);
      items.forEach((it, i) => {
        const k = ease(win(t, at[i], 0.75));
        const p = from.clone().lerp(it.to, k); p.y += Math.sin(Math.PI * k) * 1.2;
        it.m.position.copy(p); it.m.scale.setScalar(Math.max(0.001, lerp(0.25, 1, k)));
        it.m.rotation.set(lerp(-1.4, -0.12, k), lerp(0, 0.15 * (i % 2 ? 1 : -1), k) + Math.sin(t + i) * 0.05, it.rz * k);
      });
      camera.position.set(Math.sin(t * 0.12) * 1.0, 0.8, 19); camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
      items.forEach((it, i) => pin(pins[i], project, it.to.clone().add(V(0, it.round ? it.w / 2 + 0.3 : it.h / 2 + 0.3, 0))));
    };
  }

  // ── 5 · quality: four CMYK ink drops orbit and merge into a colour burst ──
  function quality(canvas) {
    const { renderer, scene, camera } = base(canvas, 38);
    const cols = [SK.c, SK.m, SK.y, SK.k];
    const drops = cols.map((c) => { const m = new THREE.Mesh(new THREE.SphereGeometry(0.9, 48, 48), new THREE.MeshPhysicalMaterial ? new THREE.MeshPhysicalMaterial({ color: c, roughness: 0.08, metalness: 0.0, clearcoat: 1, clearcoatRoughness: 0.05 }) : std(c)); scene.add(m); return m; });
    const ring = new THREE.Group(); scene.add(ring);
    const r = rng(8);
    for (let i = 0; i < 90; i++) { const c = [SK.c, SK.m, SK.y, SK.red, SK.orange, SK.navy][i % 6]; const b = new THREE.Mesh(new THREE.SphereGeometry(0.08 + r() * 0.12, 12, 12), std(c, { emissive: c, emissiveIntensity: 0.3 }));
      b.userData = { a: r() * Math.PI * 2, rad: 2.2 + r() * 2.4, y: (r() - 0.5) * 3, sp: 0.6 + r() }; ring.add(b); }
    const flash = glow(0xffffff, 12); scene.add(flash);
    const speed = []; for (let i = 0; i < 14; i++) { const l = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.04, 6), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0 })); l.position.set((r() - 0.5) * 9, (r() - 0.5) * 14, -2); scene.add(l); speed.push(l); }
    return function (t) {
      const merge = inOut(win(t, 1.3, 1.0));
      drops.forEach((d, i) => { const a = t * 1.6 + i * Math.PI / 2, rad = lerp(2.6, 0.0, merge); d.position.set(Math.cos(a) * rad, Math.sin(a * 0.7) * 0.4 + 0.5, Math.sin(a) * rad); d.scale.setScalar(Math.max(0.001, ease(win(t, 0.05 + i * 0.08, 0.4)) * (1 - 0.7 * merge))); });
      const burst = ease(win(t, 2.2, 0.8));
      ring.children.forEach((b) => { const u = b.userData; const a = u.a + t * u.sp; b.position.set(Math.cos(a) * u.rad * burst, u.y * burst + 0.5, Math.sin(a) * u.rad * burst); b.visible = burst > 0.01; });
      flash.material.opacity = 0.9 * Math.sin(Math.PI * win(t, 2.05, 0.5));
      speed.forEach((l, i) => { l.material.opacity = 0.5 * win(t, 3.0, 0.3); l.position.z = -6 + ((t * 30 + i * 3) % 18); });
      camera.position.set(Math.sin(t * 0.3) * 2, 1.2, 14); camera.lookAt(0, 0.3, 0);
      renderer.render(scene, camera);
    };
  }

  // ── 6 · for whom: individuals, companies, associations ────────────────────
  function audience(canvas, pins, at) {
    const { renderer, scene, camera, project } = base(canvas, 38);
    const person = (c) => { const g = new THREE.Group(); const h = new THREE.Mesh(new THREE.SphereGeometry(0.45, 32, 32), std(c)); h.position.y = 2.0; g.add(h);
      const b = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.75, 1.4, 32), std(c)); b.position.y = 0.95; g.add(b); return g; };
    const pads = [], tops = [];
    [-2.6, 0, 2.6].forEach((x, i) => {
      const g = new THREE.Group(); g.position.set(x, -2.8, 0); scene.add(g);
      const pad = new THREE.Mesh(new THREE.CylinderGeometry(1.35, 1.45, 0.4, 48), std([SK.red, SK.navy, SK.orange][i])); g.add(pad);
      const ico = new THREE.Group(); ico.position.y = 0.2; g.add(ico);
      if (i === 0) ico.add(person(0xf7f7fa));
      if (i === 1) { const b = new THREE.Mesh(new THREE.BoxGeometry(1.5, 3.2, 1.2), std(0xf7f7fa)); b.position.y = 1.6; ico.add(b);
        for (let r = 0; r < 5; r++) for (let c = 0; c < 3; c++) { const w = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.32, 0.05), std(SK.navy, { emissive: 0x6c8cff, emissiveIntensity: 0.25 })); w.position.set(-0.45 + c * 0.45, 0.6 + r * 0.55, 0.62); ico.add(w); } }
      if (i === 2) { [-0.65, 0, 0.65].forEach((dx, k) => { const p = person(0xf7f7fa); p.position.set(dx, 0, k === 1 ? -0.3 : 0); p.scale.setScalar(k === 1 ? 0.8 : 0.7); ico.add(p); }); }
      pads.push(g); tops.push(V(x, 1.4, 0));
    });
    return function (t) {
      pads.forEach((g, i) => { const k = back(win(t, at[i], 0.55), 1.8); g.scale.setScalar(Math.max(0.001, k)); g.rotation.y = Math.sin(t * 0.9 + i) * 0.35; });
      camera.position.set(Math.sin(t * 0.2) * 1.2, 2.2, 19); camera.lookAt(0, -0.4, 0);
      renderer.render(scene, camera);
      pins.forEach((el, i) => pin(el, project, tops[i].clone().add(V(0, i === 1 ? 0.8 : 0, 0))));
    };
  }

  window.SK3D = { idea, logoScene, textile, paper, quality, audience };
})();
