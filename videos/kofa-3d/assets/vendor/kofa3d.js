/* KOFA — 3D scene builders. builder(canvas, …) → render(t), pure function of t (seeded, no clocks).
 * Reuses the shared helpers from enx3d.js (base renderer, glow sprite, HTML pins). */
(function () {
  const { clamp, ease, inOut, back, win, rng, base: base0, glow, pin } = window.ENX3D._;
  const K = { orange: 0xeb6834, blue: 0x2a78d6, green: 0x1baf7a, yellow: 0xedA100, ink: 0x0e0e10, cream: 0xf8f3ea };
  function base(canvas, fov) { const b = base0(canvas, fov); b.scene.fog = new THREE.FogExp2(K.ink, 0.03); return b; }
  const std = (color, o = {}) => new THREE.MeshStandardMaterial(Object.assign({ color, roughness: 0.42, metalness: 0.05 }, o));

  function roundedBox(w, h, d, r, mat) {
    const s = new THREE.Shape(), x = -w / 2, y = -h / 2;
    s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r); s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r); s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
    const g = new THREE.ExtrudeGeometry(s, { depth: d, bevelEnabled: true, bevelSize: r * 0.25, bevelThickness: r * 0.25, bevelSegments: 4, curveSegments: 10 });
    g.translate(0, 0, -d / 2); return new THREE.Mesh(g, mat);
  }
  // the KOFA app tile: blue rounded square with a white K built from three bars
  function kTile(color = K.blue, letter = 0xffffff) {
    const g = new THREE.Group();
    g.add(roundedBox(2.4, 2.4, 0.5, 0.6, std(color, { roughness: 0.25, metalness: 0.1 })));
    const m = std(letter, { roughness: 0.3, emissive: letter, emissiveIntensity: 0.15 });
    const bar = (w, h, x, y, rz) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.25), m); b.position.set(x, y, 0.42); b.rotation.z = rz; g.add(b); };
    bar(0.32, 1.35, -0.38, 0, 0);
    bar(0.3, 0.92, 0.12, 0.3, -0.72);
    bar(0.3, 0.92, 0.12, -0.3, 0.72);
    return g;
  }
  function phone(w, h, screenMat) {
    const g = new THREE.Group();
    g.add(roundedBox(w, h, 0.26, 0.38, std(0x1f1f24, { metalness: 0.6, roughness: 0.3 })));
    const scr = new THREE.Mesh(new THREE.PlaneGeometry(w - 0.2, h - 0.24), screenMat || new THREE.MeshBasicMaterial({ color: 0x111114 }));
    scr.position.z = 0.26; g.add(scr);
    return { g, scr };
  }
  function steam(scene, n, seed) {
    const pos = new Float32Array(n * 3), r = rng(seed), S = [];
    for (let i = 0; i < n; i++) S.push([(r() - 0.5) * 2.2, (r() - 0.5) * 2.2, r(), 0.4 + r() * 0.6]);
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const mat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.9, map: glow(0xffffff, 1).material.map, transparent: true, opacity: 0.0, depthWrite: false });
    scene.add(new THREE.Points(geo, mat));
    return { mat, step(t, y0, rise) { for (let i = 0; i < n; i++) { const [x, z, ph, sp] = S[i]; const l = (t * sp * 0.6 + ph) % 1; pos[i * 3] = x * (1 + l) + Math.sin(l * 6 + ph * 9) * 0.3; pos[i * 3 + 1] = y0 + l * rise; pos[i * 3 + 2] = z * (1 + l); } geo.attributes.position.needsUpdate = true; } };
  }

  // ── 1 · hook: steaming plate of riz au gras, orange rim ───────────────────
  function hook(canvas) {
    const { renderer, scene, camera } = base(canvas, 40);
    const key = new THREE.SpotLight(0xffd9b0, 2.2, 40, 0.6, 0.6); key.position.set(3, 9, 4); scene.add(key);
    const plate = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.3, 0.22, 96), std(0xf3efe8, { roughness: 0.2 })); scene.add(plate);
    const rim = new THREE.Mesh(new THREE.TorusGeometry(2.55, 0.08, 16, 120), new THREE.MeshStandardMaterial({ color: K.orange, emissive: K.orange, emissiveIntensity: 0.6 }));
    rim.rotation.x = Math.PI / 2; rim.position.y = 0.12; scene.add(rim);
    const r = rng(17), N = 1700;
    const grain = new THREE.InstancedMesh(new THREE.SphereGeometry(0.05, 6, 6), std(0xe7b65a, { roughness: 0.35 }), N);
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    for (let i = 0; i < N; i++) { const a = r() * Math.PI * 2, d = Math.sqrt(r()) * 1.9; const h = 0.95 * (1 - (d / 1.9) ** 2); e.set(r() * 3, r() * 3, r() * 3); q.setFromEuler(e);
      m4.compose(new THREE.Vector3(Math.cos(a) * d, 0.12 + h * r(), Math.sin(a) * d), q, new THREE.Vector3(1, 1.8, 1)); grain.setMatrixAt(i, m4); }
    scene.add(grain);
    const meat = std(0x7a3b16, { roughness: 0.3, metalness: 0.1 });
    [[-0.5, 0.95, 0.2, 0.5], [0.45, 0.9, -0.25, -0.4], [0.05, 1.05, 0.55, 1.2]].forEach(([x, y, z, ry]) => { const c = new THREE.Mesh(new THREE.SphereGeometry(0.5, 24, 24), meat); c.scale.set(1.3, 0.55, 0.8); c.position.set(x, y, z); c.rotation.y = ry; scene.add(c); });
    for (let i = 0; i < 18; i++) { const c = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.05, 0.12), std(i % 2 ? 0x2f8f3a : 0xd9472b)); c.position.set((r() - 0.5) * 2.4, 0.9 + r() * 0.3, (r() - 0.5) * 2.4); scene.add(c); }
    const st = steam(scene, 120, 5);
    const og = glow(K.orange, 9); og.position.set(0, 0, -1); scene.add(og);
    return function (t) {
      st.step(t, 1.0, 4.2); st.mat.opacity = 0.35 * ease(win(t, 0.1, 0.6));
      rim.material.emissiveIntensity = 0.6 + 1.6 * ease(win(t, 1.3, 0.6));
      og.material.opacity = 0.35 + 0.4 * ease(win(t, 1.3, 0.6));
      const push = ease(win(t, 0, 1.9));
      const d = 15 - push * 4.5, a = 0.15 + t * 0.25 + Math.pow(clamp((t - 1.55) / 0.45), 3) * 1.6; // whip at the end
      camera.position.set(Math.sin(a) * d * 0.55, 7.5 - push * 1.5, Math.cos(a) * d * 0.55);
      camera.lookAt(0, 0.55, 0);
      renderer.render(scene, camera);
    };
  }

  // ── 2 & 9 · K tile on orange ──────────────────────────────────────────────
  function logo(canvas, o = {}) {
    const { renderer, scene, camera } = base(canvas, 35);
    scene.fog = null;
    const T = kTile(o.white ? 0xffffff : K.blue, o.white ? K.orange : 0xffffff); scene.add(T);
    const sweep = new THREE.PointLight(0xffffff, 0, 8); scene.add(sweep);
    const shadow = glow(0x5a1e06, 4.5); shadow.position.set(0, -2.1, -0.5); shadow.material.blending = THREE.NormalBlending; scene.add(shadow);
    return function (t) {
      const k = back(win(t, 0, 0.7), 1.8);
      T.position.y = o.y0 + (1 - k) * -7;
      T.rotation.y = (1 - ease(win(t, 0, 0.9))) * 1.4 + Math.sin(t * 1.2) * 0.18;
      T.rotation.x = Math.sin(t * 0.9) * 0.08;
      T.scale.setScalar(o.scale || 1);
      const sx = -3 + 6 * inOut(win(t, 0.8, 1.0)); sweep.position.set(sx, o.y0 + 1, 2.2); sweep.intensity = 3 * Math.sin(Math.PI * win(t, 0.8, 1.0));
      shadow.material.opacity = 0.5 * ease(win(t, 0.3, 0.5)); shadow.position.y = o.y0 - 2.1;
      camera.position.set(0, 0, 13); camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
    };
  }

  // ── 3 · four clay icons ───────────────────────────────────────────────────
  function categories(canvas, labels, at) {
    const { renderer, scene, camera, project } = base(canvas, 36);
    const pads = [0x3a2018, 0x13301f, 0x1c2140, 0x332a12];
    const items = [];
    const mkPlate = () => { const g = new THREE.Group(); const p = new THREE.Mesh(new THREE.CylinderGeometry(0.75, 0.62, 0.12, 48), std(0xf4f1ea, { roughness: 0.2 })); g.add(p);
      const f = new THREE.Mesh(new THREE.BoxGeometry(0.06, 1.2, 0.06), std(0xd1d5db, { metalness: 0.8 })); f.position.set(-0.95, 0.3, 0); g.add(f); const kn = f.clone(); kn.position.x = 0.95; g.add(kn); return g; };
    const mkCart = () => { const g = new THREE.Group(); const b = new THREE.Mesh(new THREE.BoxGeometry(1.3, 0.7, 0.8), std(0xb8c2cc, { metalness: 0.5, roughness: 0.3 })); b.position.y = 0.45; g.add(b);
      [[-0.45, -0.3], [0.45, -0.3], [-0.45, 0.3], [0.45, 0.3]].forEach(([x, z]) => { const w = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.05, 8, 16), std(0x1f2937)); w.position.set(x, 0, z); g.add(w); });
      [[0x2f8f3a, -0.3], [0xd9472b, 0.1], [0xedA100, 0.4]].forEach(([c, x]) => { const v = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 16), std(c)); v.position.set(x, 0.9, 0); g.add(v); }); return g; };
    const mkBox = () => { const g = new THREE.Group(); const b = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.9, 1.0), std(0xc08a4e, { roughness: 0.8 })); b.position.y = 0.45; g.add(b);
      const tape = new THREE.Mesh(new THREE.BoxGeometry(1.22, 0.92, 0.18), std(0xe7d3a8)); tape.position.y = 0.45; g.add(tape); return g; };
    const mkSkewer = () => { const g = new THREE.Group(); const s = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 2.0, 8), std(0xd6b98c)); s.rotation.z = 0.6; s.position.y = 0.55; g.add(s);
      for (let i = 0; i < 4; i++) { const c = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.32, 0.32), std(i % 2 ? 0x7a3b16 : 0x9a4a1c, { roughness: 0.4 })); c.position.set(-0.5 + i * 0.32, 0.25 + i * 0.22, 0); c.rotation.set(0.3, 0.5, 0.2); g.add(c); } return g; };
    [mkPlate, mkCart, mkBox, mkSkewer].forEach((f, i) => {
      const g = new THREE.Group(); const x = i % 2 ? 1.75 : -1.75, y = i < 2 ? 1.9 : -1.9; g.position.set(x, y, 0); scene.add(g);
      const pad = new THREE.Mesh(new THREE.CylinderGeometry(1.35, 1.35, 0.25, 64), std(pads[i], { roughness: 0.6 })); pad.rotation.x = Math.PI / 2 - 0.45; pad.position.z = -0.35; g.add(pad);
      const icon = f(); icon.rotation.x = 0.45; icon.position.set(0, -0.3, 0.3); g.add(icon);
      items.push({ g, icon, top: new THREE.Vector3(x, y - 1.55, 0.4) });
    });
    const og = glow(K.orange, 10); og.position.set(0, 0, -3); og.material.opacity = 0.35; scene.add(og);
    return function (t) {
      items.forEach(({ g, icon }, i) => { g.scale.setScalar(Math.max(0.001, back(win(t, at[i], 0.45), 2))); icon.rotation.y = t * 0.8 + i; });
      camera.position.set(Math.sin(t * 0.25) * 1.2, 0.4, 19); camera.lookAt(0, -0.1, 0);
      renderer.render(scene, camera);
      items.forEach(({ top }, i) => pin(labels[i], project, top, 0, 0));
    };
  }

  // ── 4 · phone with the real KOFA home screen, scrolling ───────────────────
  function app(canvas, pins) {
    const { renderer, scene, camera, project } = base(canvas, 36);
    window.__hf = window.__hf || {}; window.__hf.buildReady = window.__hf.buildReady || {};
    let tex; window.__hf.buildReady["kofa-app-screen"] = new Promise((res) => { tex = new THREE.TextureLoader().load("assets/screen-accueil.png", res, undefined, res); });
    tex.encoding = THREE.sRGBEncoding; tex.repeat.set(1, 0.62); tex.offset.set(0, 0.38);
    const P = phone(3.2, 6.4, new THREE.MeshBasicMaterial({ map: tex })); scene.add(P.g);
    const og = glow(K.orange, 11); og.position.set(0, 0, -2.5); og.material.opacity = 0.45; scene.add(og);
    const r = rng(4);
    for (let i = 0; i < 14; i++) { const c = new THREE.Mesh(new THREE.SphereGeometry(0.08 + r() * 0.1, 12, 12), new THREE.MeshBasicMaterial({ color: i % 3 ? K.orange : 0xffc49b })); c.position.set((r() - 0.5) * 8, (r() - 0.5) * 11, -1 - r() * 3); scene.add(c); }
    const tapP = new THREE.Vector3(0.9, -0.35, 0.25);
    return function (t) {
      P.g.position.y = (1 - ease(win(t, 0, 0.7))) * -9 + Math.sin(t * 1.4) * 0.08;
      P.g.rotation.y = -0.32 + 0.22 * ease(win(t, 0, 1.4)) + Math.sin(t * 0.6) * 0.05;
      P.g.rotation.x = -0.06;
      tex.offset.y = 0.38 - 0.24 * inOut(win(t, 0.9, 1.3));
      camera.position.set(0, 0.2, 16.5); camera.lookAt(0, -0.3, 0);
      renderer.render(scene, camera);
      P.g.updateMatrixWorld(); pin(pins[0], project, tapP.clone().applyMatrix4(P.g.matrixWorld), 0, 0);
    };
  }

  // ── 5 · rider on a motorbike through the city ─────────────────────────────
  function rider(canvas, pins) {
    const { renderer, scene, camera, project } = base(canvas, 42);
    scene.fog = new THREE.FogExp2(0x1a0f0a, 0.045);
    const road = new THREE.Mesh(new THREE.PlaneGeometry(10, 400), std(0x1c1c20, { roughness: 0.9 })); road.rotation.x = -Math.PI / 2; scene.add(road);
    const side = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), std(0x241712, { roughness: 1 })); side.rotation.x = -Math.PI / 2; side.position.y = -0.02; scene.add(side);
    const dashes = []; for (let i = 0; i < 30; i++) { const d = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.02, 1.4), new THREE.MeshBasicMaterial({ color: 0xf5d68a })); scene.add(d); dashes.push(d); }
    const r = rng(23), blds = [];
    for (let i = 0; i < 26; i++) { const h = 2 + r() * 5, w = 2 + r() * 2; const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, w), std([0x5b3a29, 0x6b4a33, 0x3d2a20, 0x7a5236][i % 4], { roughness: 0.9 }));
      m.userData = { side: i % 2 ? 1 : -1, z0: i * 7, h, w }; scene.add(m); blds.push(m);
      const lamp = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.3, 0.05), new THREE.MeshBasicMaterial({ color: 0xffc46b })); lamp.position.set(0, h * 0.2, w / 2 + 0.03); m.add(lamp); }
    const sun = glow(0xff8a3d, 30); sun.position.set(0, 6, -60); sun.material.opacity = 0.6; scene.add(sun);
    // motorbike + rider
    const B = new THREE.Group(); scene.add(B);
    const wheel = () => { const w = new THREE.Group(); w.add(new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.12, 12, 32), std(0x111111))); const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.2, 16), std(0x9ca3af, { metalness: 0.8 })); hub.rotation.x = Math.PI / 2; w.add(hub);
      for (let i = 0; i < 3; i++) { const s = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.7, 0.04), std(0x9ca3af, { metalness: 0.8 })); s.rotation.z = i * Math.PI / 3; w.add(s); } w.rotation.y = Math.PI / 2; return w; };
    const wf = wheel(), wr = wheel(); wf.position.set(0, 0.54, -1.05); wr.position.set(0, 0.54, 1.0); B.add(wf); B.add(wr);
    const frame = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.45, 1.8), std(0xc0262d, { metalness: 0.3, roughness: 0.35 })); frame.position.set(0, 0.95, 0); B.add(frame);
    const seat = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.14, 0.9), std(0x111111)); seat.position.set(0, 1.24, 0.25); B.add(seat);
    const bars = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.9, 8), std(0x9ca3af, { metalness: 0.8 })); bars.rotation.z = Math.PI / 2; bars.position.set(0, 1.55, -0.8); B.add(bars);
    const lamp = glow(0xfff1c2, 2.2); lamp.position.set(0, 1.25, -1.25); B.add(lamp);
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.32, 0.9, 16), std(0x2a78d6)); body.position.set(0, 1.75, 0.1); body.rotation.x = -0.35; B.add(body);
    const helm = new THREE.Mesh(new THREE.SphereGeometry(0.26, 24, 24), std(0xf8f3ea, { roughness: 0.2 })); helm.position.set(0, 2.32, -0.12); B.add(helm);
    const boxM = std(K.orange, { roughness: 0.4 });
    const box = roundedBox(0.95, 0.85, 0.8, 0.12, boxM); box.position.set(0, 1.85, 0.95); box.rotation.y = Math.PI / 2; B.add(box);
    const boxTop = new THREE.Vector3(0.5, 2.45, 0.95);
    return function (t) {
      // speed ramp: fast → slow-motion dip (1.0–2.0 s) → fast; distance is the integral, so it stays seek-safe
      const sm = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
      const dist = 22 * t - 9 * sm((t - 1.0) / 1.0);
      dashes.forEach((d, i) => { d.position.set(0, 0.01, ((i * 4 + dist) % 120) - 100); });
      blds.forEach((m) => { const z = ((m.userData.z0 + dist) % 180) - 160; m.position.set(m.userData.side * (6 + m.userData.w), m.userData.h / 2, z); });
      wf.rotation.x = -dist * 2.2; wr.rotation.x = -dist * 2.2;
      B.position.y = Math.sin(t * 24) * 0.02; B.rotation.z = Math.sin(t * 1.3) * 0.06;
      camera.position.set(5.2 + Math.sin(t * 0.8) * 0.2, 2.0, -5.5 + t * 0.4); camera.lookAt(0, 1.3, 0.2);
      renderer.render(scene, camera);
      B.updateMatrixWorld(); pin(pins[0], project, boxTop.clone().applyMatrix4(B.matrixWorld), 0, -10);
    };
  }

  // ── 6 · voice note: yellow waveform bursting out of a phone ───────────────
  function vocal(canvas, at) {
    const { renderer, scene, camera } = base(canvas, 38);
    const P = phone(3.0, 6.0); scene.add(P.g);
    const mic = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.12, 48), std(K.orange, { emissive: K.orange, emissiveIntensity: 0.4 })); mic.rotation.x = Math.PI / 2; mic.position.set(0, -2.1, 0.3); P.g.add(mic);
    const N = 21, bars = [];
    for (let i = 0; i < N; i++) { const b = new THREE.Mesh(new THREE.BoxGeometry(0.14, 1, 0.14), std(K.yellow, { emissive: K.yellow, emissiveIntensity: 0.5, roughness: 0.3 })); b.position.set(-2.1 + i * 0.21, 0.4, 0.9); scene.add(b); bars.push(b); }
    const yg = glow(K.yellow, 6); yg.position.set(0, 0.4, 0.6); scene.add(yg);
    const H = [0.4, 0.9, 1.6, 2.3, 1.2, 2.8, 1.8, 0.9, 2.4, 3.1, 1.6, 2.2, 1.1, 2.6, 1.9, 0.8, 2.2, 1.4, 0.7, 1.2, 0.5];
    return function (t) {
      P.g.rotation.y = 0.35 - 0.2 * ease(win(t, 0, 1.2)) + Math.sin(t * 0.7) * 0.05; P.g.position.y = (1 - ease(win(t, 0, 0.6))) * -8;
      const rec = ease(win(t, at.rec, 0.3)), done = ease(win(t, at.done, 0.4));
      mic.scale.setScalar(1 + 0.25 * rec * (0.5 + 0.5 * Math.sin(t * 10)));
      bars.forEach((b, i) => { const h = Math.max(0.05, rec * H[i] * (0.65 + 0.35 * Math.sin(t * 9 + i * 1.7)) * (1 - 0.7 * done)); b.scale.y = h; });
      yg.material.opacity = 0.55 * rec;
      camera.position.set(Math.sin(t * 0.2) * 0.8, 0.4, 17); camera.lookAt(0, -0.5, 0);
      renderer.render(scene, camera);
    };
  }

  // ── 7 · four code tiles flipping in, turning green ────────────────────────
  function code(canvas, labels, at, okAt) {
    const { renderer, scene, camera, project } = base(canvas, 36);
    const tiles = [0, 1, 2, 3].map((i) => { const m = roundedBox(1.25, 1.6, 0.35, 0.25, std(0x1a1a1d, { emissive: K.orange, emissiveIntensity: 0.0, roughness: 0.35 })); m.position.set(-2.1 + i * 1.4, 0, 0); scene.add(m); return m; });
    const og = glow(K.orange, 9); og.position.set(0, 0, -1.5); scene.add(og);
    const gg = glow(K.green, 10); gg.position.set(0, 0, -1.2); scene.add(gg);
    const cO = new THREE.Color(K.orange), cG = new THREE.Color(K.green);
    return function (t) {
      const ok = ease(win(t, okAt, 0.5));
      tiles.forEach((m, i) => { const k = ease(win(t, at[i], 0.45)); m.rotation.x = (1 - k) * -Math.PI / 2; m.scale.setScalar(Math.max(0.001, back(win(t, at[i] - 0.1, 0.4), 1.6)));
        m.material.emissive.copy(cO).lerp(cG, ok); m.material.emissiveIntensity = 0.25 * k + 0.35 * ok; m.position.y = Math.sin(t * 2 + i) * 0.05; });
      og.material.opacity = 0.5 * (1 - ok); gg.material.opacity = 0.6 * ok;
      camera.position.set(Math.sin(t * 0.3) * 1.0, 1.2, 15.5); camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
      tiles.forEach((m, i) => pin(labels[i], project, new THREE.Vector3(m.position.x, m.position.y, 0.3), 0, 0));
    };
  }

  Object.assign(window.ENX3D, { k: { hook, logo, categories, app, rider, vocal, code } });
})();
