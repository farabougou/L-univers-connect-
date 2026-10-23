/* Enoryx « à distance » — globe, liaison bâtiment → téléphone, consommation en hologramme.
 * Same contract as enx3d.js: builder(canvas, …) → render(t), pure function of t. Needs land.js. */
(function () {
  const { C, clamp, ease, inOut, back, win, base, glow, pin } = window.ENX3D._;
  const R = 3;
  const toV = (lon, lat, r = R) => { const a = lon * Math.PI / 180, b = lat * Math.PI / 180; return new THREE.Vector3(r * Math.cos(b) * Math.sin(a), r * Math.sin(b), r * Math.cos(b) * Math.cos(a)); };
  const CITY = { Paris: [2.35, 48.86], Dakar: [-17.45, 14.69], "New York": [-74, 40.71], Dubaï: [55.27, 25.2], Bamako: [-8, 12.64] };

  function earth(scene, dot = 0x38bdf8, atmC = 0x2563eb) {
    const g = new THREE.Group(); scene.add(g);
    g.add(new THREE.Mesh(new THREE.SphereGeometry(R * 0.995, 64, 64), new THREE.MeshStandardMaterial({ color: 0x081634, roughness: 0.9, metalness: 0.1, emissive: 0x04102a, emissiveIntensity: 0.6 })));
    const L = window.ENX_LAND, pos = new Float32Array(L.length / 2 * 3);
    for (let i = 0; i < L.length / 2; i++) { const v = toV(L[i * 2], L[i * 2 + 1], R * 1.004); pos[i * 3] = v.x; pos[i * 3 + 1] = v.y; pos[i * 3 + 2] = v.z; }
    const pg = new THREE.BufferGeometry(); pg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const tex = glow(0xffffff, 1).material.map;
    g.add(new THREE.Points(pg, new THREE.PointsMaterial({ color: dot, size: 0.085, map: tex, transparent: true, opacity: 0.95, depthWrite: false })));
    const atm = glow(atmC, R * 3.1); atm.material.opacity = 0.55; scene.add(atm);
    return g;
  }
  function arc(g, from, to, color, h = 0.28) {
    const a = toV(...from).normalize(), b = toV(...to).normalize(), pts = [];
    for (let i = 0; i <= 64; i++) { const t = i / 64; const v = new THREE.Vector3().copy(a).lerp(b, t).normalize(); pts.push(v.multiplyScalar(R * (1.01 + h * Math.sin(Math.PI * t)))); }
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.95 }));
    line.geometry.setDrawRange(0, 0); g.add(line);
    const head = glow(color, 0.55); g.add(head);
    return { line, pts, head, set(k) { const n = Math.floor(k * 64); line.geometry.setDrawRange(0, n + 1); head.position.copy(pts[Math.min(64, n)]); head.material.opacity = k > 0 && k < 1 ? 1 : 0; } };
  }
  function marker(g, ll, color, size = 0.09) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(size, 16, 16), new THREE.MeshBasicMaterial({ color })); m.position.copy(toV(...ll, R * 1.01)); g.add(m);
    const h = glow(color, 0.8); h.position.copy(m.position); g.add(h);
    return { m, h };
  }

  // ── 1 & 5 · globe: cities light up, arcs to Bamako (or an alert travelling out of Bamako) ──
  function globe(canvas, labels, o) {
    const { renderer, scene, camera, project } = base(canvas, 34);
    scene.fog = null;
    const g = earth(scene, o.dot, o.atm); g.rotation.y = 0.42; g.rotation.x = -0.12;
    const alert = o.mode === "alert";
    const names = o.cities;
    const mk = names.map((n) => marker(g, CITY[n], alert ? 0xf8fafc : (o.city || C.cyan)));
    const bko = marker(g, CITY.Bamako, alert ? 0xdc2626 : C.orange, 0.12);
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.12, 0.17, 48), new THREE.MeshBasicMaterial({ color: alert ? 0xdc2626 : C.orange, transparent: true, side: THREE.DoubleSide }));
    ring.position.copy(toV(...CITY.Bamako, R * 1.012)); ring.lookAt(new THREE.Vector3()); g.add(ring);
    const arcs = names.map((n) => alert ? arc(g, CITY.Bamako, CITY[n], 0xdc2626, 0.32) : arc(g, CITY[n], CITY.Bamako, C.orange, 0.3));
    const tmp = new THREE.Vector3();
    return function (t) {
      g.rotation.y = 0.42 + t * 0.03;
      mk.forEach((M, i) => { const k = ease(win(t, o.at[i], 0.4)); M.m.scale.setScalar(Math.max(0.001, k)); M.h.material.opacity = k; });
      const kb = ease(win(t, o.bko, 0.5)); bko.m.scale.setScalar(Math.max(0.001, kb)); bko.h.material.opacity = kb;
      const ph = ((t - o.bko) % 1.1 + 1.1) % 1.1 / 1.1;
      ring.scale.setScalar(t > o.bko ? 1 + ph * 3.5 : 0.001); ring.material.opacity = t > o.bko ? (1 - ph) : 0;
      arcs.forEach((A, i) => A.set(inOut(win(t, o.arcs + i * 0.18, 1.1))));
      const z = 20 - ease(win(t, o.zoomAt || 99, 2.2)) * 3;
      camera.position.set(0.0, 0.6, z); camera.lookAt(0, 0.3, 0);
      renderer.render(scene, camera);
      names.forEach((n, i) => { const el = labels[i]; if (!el) return; g.localToWorld(tmp.copy(toV(...CITY[n], R * 1.01))); pin(el, project, tmp, 0, -14); });
      if (labels.bko) { g.localToWorld(tmp.copy(toV(...CITY.Bamako, R * 1.01))); pin(labels.bko, project, tmp, 0, 74); }
    };
  }

  // phone body (screen faces +z)
  function phone(scene, w = 2.6, h = 5.2) {
    const g = new THREE.Group(); scene.add(g);
    const shape = new THREE.Shape(); const r = 0.42, x = -w / 2, y = -h / 2;
    shape.moveTo(x + r, y); shape.lineTo(x + w - r, y); shape.quadraticCurveTo(x + w, y, x + w, y + r); shape.lineTo(x + w, y + h - r); shape.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    shape.lineTo(x + r, y + h); shape.quadraticCurveTo(x, y + h, x, y + h - r); shape.lineTo(x, y + r); shape.quadraticCurveTo(x, y, x + r, y);
    const body = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.22, bevelEnabled: true, bevelSize: 0.05, bevelThickness: 0.05, bevelSegments: 3 }), new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.6, roughness: 0.3 }));
    body.position.z = -0.22; g.add(body);
    const scr = new THREE.Mesh(new THREE.PlaneGeometry(w - 0.24, h - 0.3), new THREE.MeshBasicMaterial({ color: 0x07122a })); scr.position.z = 0.06; g.add(scr);
    const glowS = glow(C.cyan, 6); glowS.position.z = -0.6; glowS.material.opacity = 0.35; g.add(glowS);
    return { g, scr };
  }

  // ── 2 · Bamako building → data beam → phone anywhere ─────────────────────
  function link(canvas, pins) {
    const { renderer, scene, camera, project } = base(canvas, 40);
    scene.fog = null;
    const g = earth(scene); g.scale.setScalar(0.5); g.position.set(0, 3.9, -2); g.rotation.y = 0.42;
    const bkoLocal = toV(...CITY.Bamako, R * 1.02);
    const P = phone(scene, 2.0, 4.0); P.g.position.set(0, -1.0, 0);
    const pts = []; const tmp = new THREE.Vector3();
    const curve = () => { g.localToWorld(tmp.copy(bkoLocal)); return new THREE.CatmullRomCurve3([tmp.clone(), new THREE.Vector3(2.0, 3.0, 1), new THREE.Vector3(-1.3, 2.0, 1.2), new THREE.Vector3(0, 1.05, 0.3)]); };
    let cv = curve();
    const beam = new THREE.Mesh(new THREE.TubeGeometry(cv, 120, 0.035, 8, false), new THREE.MeshBasicMaterial({ color: C.cyan, transparent: true, opacity: 0.85 }));
    scene.add(beam); const cnt = beam.geometry.index.count;
    const packets = [0, 1, 2, 3, 4].map(() => { const s = glow(0xbae6fd, 0.6); scene.add(s); return s; });
    const bk = glow(C.orange, 1.3); scene.add(bk);
    return function (t) {
      g.rotation.y = 0.42 + t * 0.02;
      P.g.rotation.y = -0.25 + Math.sin(t * 0.5) * 0.12; P.g.rotation.x = -0.08;
      P.g.position.y = -1.0 + (1 - ease(win(t, 0.2, 0.9))) * -4;
      beam.geometry.setDrawRange(0, Math.floor(cnt * inOut(win(t, 1.0, 1.3)) / 3) * 3);
      packets.forEach((s, i) => { const ph = (t - 2.3 - i * 0.28) / 1.2; const on = ph > 0 && ph < 8; const f = on ? ph % 1 : 0; s.position.copy(cv.getPoint(f)); s.material.opacity = on ? Math.sin(f * Math.PI) : 0; });
      g.localToWorld(tmp.copy(bkoLocal)); bk.position.copy(tmp); bk.material.opacity = 0.7 + 0.3 * Math.sin(t * 5);
      camera.position.set(Math.sin(t * 0.05) * 1.5, 0.6, 15.5); camera.lookAt(0, 0.4, 0);
      renderer.render(scene, camera);
      P.g.updateMatrixWorld(); pin(pins[0], project, new THREE.Vector3(0, 0, 0.1).applyMatrix4(P.g.matrixWorld), 0, 0);
      pin(pins[1], project, tmp, 0, -30);
    };
  }

  // ── 3 · live consumption: hologram bars rising out of the phone ──────────
  function conso(canvas, o) {
    const { renderer, scene, camera } = base(canvas, 38);
    scene.fog = null;
    const P = phone(scene, 3.4, 6.6); P.g.rotation.x = -1.12; P.g.position.set(0, -2.2, 0);
    const N = 24, bars = [];
    const prof = (i) => 0.35 + 0.65 * (0.5 + 0.5 * Math.sin((i - 7) / 24 * Math.PI * 2)) * (i > 7 && i < 20 ? 1 : 0.55);
    for (let i = 0; i < N; i++) {
      const c = i === o.peak ? C.orange : C.cyan;
      const m = new THREE.Mesh(new THREE.BoxGeometry(0.1, 1, 0.1), new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.85 }));
      const col = i % 6, row = Math.floor(i / 6);
      m.position.set(-1.1 + col * 0.44, -1.6 + row * 0.9, 0.1); P.g.add(m); m.userData = { h: prof(i) * 2.4 * (i === o.peak ? 1.25 : 1) };
      m.rotation.x = Math.PI / 2; bars.push(m);
    }
    const holo = glow(C.cyan, 7); holo.position.set(0, -0.8, 0); scene.add(holo);
    return function (t) {
      bars.forEach((m, i) => {
        const k = ease(win(t, o.start + i * 0.05, 0.6)), live = 1 + 0.08 * Math.sin(t * 3 + i);
        const h = Math.max(0.001, m.userData.h * k * live);
        m.scale.y = h;                 // box is rotated so its local y runs along the phone normal (+z)
        m.position.z = 0.08 + h / 2;   // stand on the glass
      });
      holo.material.opacity = 0.5 * ease(win(t, o.start, 0.8));
      P.g.rotation.z = Math.sin(t * 0.3) * 0.12 - 0.15;
      camera.position.set(Math.sin(t * 0.06) * 2, 5.5, 17); camera.lookAt(0, -0.6, 0);
      renderer.render(scene, camera);
    };
  }

  Object.assign(window.ENX3D, { globe, link, conso });
})();
