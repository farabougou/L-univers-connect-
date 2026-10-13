/* Enoryx — publicité. Same contract as enx3d.js: builder(canvas, …) → render(t), pure function of t.
 * Needs enx3d.js (shared helpers) and font-bold.js (Helvetiker Bold typeface for the 3D wordmark). */
(function () {
  const { C, clamp, ease, inOut, back, win, rng, base, glow, pin, grid, mark, animMark } = window.ENX3D._;
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const GOLD = 0xf5b301, RED = 0xdc2626, YEL = 0xeab308;

  // ── typeface → extruded letters ──────────────────────────────────────────
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
  function word3d(str, size, depth, mats) {
    const grp = new THREE.Group(); let x = 0; const letters = [];
    [...str].forEach((ch) => {
      const { shapes, adv } = glyphShapes(ch, size);
      if (shapes.length) {
        const geo = new THREE.ExtrudeGeometry(shapes, { depth, bevelEnabled: true, bevelThickness: size * 0.04, bevelSize: size * 0.025, bevelSegments: 3, curveSegments: 10 });
        geo.computeBoundingBox(); const bb = geo.boundingBox, cx = (bb.max.x + bb.min.x) / 2, cy = (bb.max.y + bb.min.y) / 2;
        geo.translate(-cx, -cy, -depth / 2);
        const holder = new THREE.Group(); holder.position.x = x + cx; holder.userData.cy = cy;
        holder.add(new THREE.Mesh(geo, mats)); grp.add(holder); letters.push(holder);
      }
      x += adv;
    });
    letters.forEach((l) => { l.position.x -= x / 2; l.position.y = l.userData.cy - size * 0.36; l.userData.home = l.position.clone(); });
    grp.userData.letters = letters; return grp;
  }
  function stars(scene, n, seed, spread, color = 0x7dd3fc, size = 0.07) {
    const r = rng(seed), pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { pos[i * 3] = (r() - 0.5) * spread; pos[i * 3 + 1] = (r() - 0.5) * spread * 1.6; pos[i * 3 + 2] = -4 - r() * spread * 0.6; }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const p = new THREE.Points(g, new THREE.PointsMaterial({ color, size, transparent: true, opacity: 0.55, depthWrite: false })); scene.add(p); return p;
  }
  function coin(r = 0.34) {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, r * 0.22, 32), new THREE.MeshStandardMaterial({ color: GOLD, metalness: 0.75, roughness: 0.28, emissive: 0x5a3a00, emissiveIntensity: 0.4 }));
    return m;
  }

  // ── 1 · bill gauge: needle climbs into the red, money falls through ───────
  function meter(canvas) {
    const { renderer, scene, camera } = base(canvas, 38);
    scene.fog = null;
    stars(scene, 260, 5, 30, 0x334155, 0.06);
    const G = new THREE.Group(); scene.add(G);
    const RAD = 2.35, A0 = Math.PI * 7 / 6, SW = Math.PI * 4 / 3;      // 240° sweep, left → right
    const rim = new THREE.Mesh(new THREE.TorusGeometry(RAD + 0.5, 0.12, 24, 160), new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.85, roughness: 0.25 }));
    G.add(rim);
    const face = new THREE.Mesh(new THREE.CylinderGeometry(RAD + 0.45, RAD + 0.45, 0.3, 96), new THREE.MeshStandardMaterial({ color: 0x0a1328, metalness: 0.3, roughness: 0.6 }));
    face.rotation.x = Math.PI / 2; face.position.z = -0.2; G.add(face);
    const N = 42, ticks = [];
    const cA = new THREE.Color(C.green), cB = new THREE.Color(YEL), cC = new THREE.Color(C.orange), cD = new THREE.Color(RED);
    for (let i = 0; i < N; i++) {
      const k = i / (N - 1), a = A0 - k * SW;
      const col = k < 0.4 ? cA.clone().lerp(cB, k / 0.4) : k < 0.7 ? cB.clone().lerp(cC, (k - 0.4) / 0.3) : cC.clone().lerp(cD, (k - 0.7) / 0.3);
      const m = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.42, 0.12), new THREE.MeshStandardMaterial({ color: 0x1e293b, emissive: col, emissiveIntensity: 0 }));
      m.position.set(Math.cos(a) * RAD, Math.sin(a) * RAD, 0); m.rotation.z = a - Math.PI / 2; m.userData = { k, col }; G.add(m); ticks.push(m);
    }
    const piv = new THREE.Group(); G.add(piv); piv.position.z = 0.2;
    const needle = new THREE.Mesh(new THREE.BoxGeometry(0.1, RAD * 0.95, 0.08), new THREE.MeshStandardMaterial({ color: 0xf8fafc, emissive: 0xffffff, emissiveIntensity: 0.4 }));
    needle.position.y = RAD * 0.42; piv.add(needle);
    const tip = glow(RED, 1.1); tip.position.y = RAD * 0.88; piv.add(tip);
    const hubM = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.3, 48), new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.9, roughness: 0.2 }));
    hubM.rotation.x = Math.PI / 2; hubM.position.z = 0.25; G.add(hubM);
    const redGlow = glow(RED, 11); redGlow.position.set(1.4, 1.2, -1.5); scene.add(redGlow);
    const r = rng(9), coins = [];
    for (let i = 0; i < 26; i++) { const c = coin(0.22 + r() * 0.16); c.userData = { x: (r() - 0.5) * 7, z: -3.5 + r() * 2.5, ph: r(), sp: 0.28 + r() * 0.25, rx: r() * 6, ry: r() * 6 }; scene.add(c); coins.push(c); }
    const sparks = [0, 1, 2, 3, 4, 5].map(() => { const s = glow(0xffb347, 0.5); G.add(s); return s; });
    return function (t) {
      const v = 0.12 + 0.82 * inOut(win(t, 0.25, 2.2)) + (t > 2.3 ? 0.012 * Math.sin(t * 38) : 0);
      piv.rotation.z = (A0 - v * SW) - Math.PI / 2;
      ticks.forEach((m) => { m.material.emissiveIntensity = m.userData.k <= v ? 1.4 : 0.06; m.material.color.copy(m.userData.k <= v ? m.userData.col : new THREE.Color(0x1e293b)); });
      const hot = ease(win(v, 0.68, 0.2));
      redGlow.material.opacity = 0.55 * hot * (0.8 + 0.2 * Math.sin(t * 9));
      tip.material.opacity = 0.3 + 0.7 * hot;
      const ta = A0 - v * SW;
      sparks.forEach((s, i) => { const ph = ((t * 2.2 + i / 6) % 1); s.position.set(Math.cos(ta) * (RAD + ph * 0.9) + Math.sin(i * 7) * ph * 0.5, Math.sin(ta) * (RAD + ph * 0.9) + ph * 0.6, 0.4); s.material.opacity = hot * (1 - ph); });
      coins.forEach((c) => { const u = c.userData, life = (t * u.sp + u.ph) % 1; c.position.set(u.x, 8 - life * 16, u.z); c.rotation.set(u.rx + t * 2.4, u.ry + t * 1.7, 0); });
      G.rotation.y = Math.sin(t * 0.6) * 0.18 - 0.08; G.rotation.x = -0.06;
      G.scale.setScalar(Math.max(0.001, back(win(t, 0, 0.55), 1.5)));
      const z = 21 - ease(win(t, 0, 3.6)) * 1.8;
      camera.position.set(0.3, 0.2, z); camera.lookAt(0, -0.6, 0);
      renderer.render(scene, camera);
    };
  }

  // ── 3 & 7 · 3D wordmark: letters fly in and lock, orbital mark behind ─────
  function brand(canvas, o = {}) {
    const T0 = o.t0 == null ? 0.15 : o.t0, END = !!o.end;
    const { renderer, scene, camera } = base(canvas, 38);
    scene.fog = null;
    const st = stars(scene, 420, 11, 34);
    const face = new THREE.MeshStandardMaterial({ color: 0xf8fafc, metalness: 0.35, roughness: 0.22, emissive: 0x7dd3fc, emissiveIntensity: 0.18 });
    const side = new THREE.MeshStandardMaterial({ color: 0x1d4ed8, metalness: 0.6, roughness: 0.3, emissive: 0x1d4ed8, emissiveIntensity: 0.55 });
    const W3 = word3d("ENORYX", 0.8, 0.34, [face, side]); scene.add(W3);
    const L = W3.userData.letters, r = rng(21);
    L.forEach((l, i) => { l.userData.from = V((r() - 0.5) * 16, (r() - 0.5) * 18, 6 + r() * 8); l.userData.rot = V((r() - 0.5) * 6, (r() - 0.5) * 6, (r() - 0.5) * 3); });
    const M = mark(0.95); M.g.position.set(0, END ? 2.1 : 0, -3); scene.add(M.g);
    const sweep = new THREE.PointLight(0xbae6fd, 0, 7); scene.add(sweep);
    const burst = glow(C.cyan, 1); scene.add(burst);
    const NB = 90, bp = new Float32Array(NB * 3), dirs = [];
    for (let i = 0; i < NB; i++) { const a = r() * Math.PI * 2, b = (r() - 0.5) * 1.6; dirs.push(V(Math.cos(a) * Math.cos(b), Math.sin(b) * 1.4, Math.sin(a) * Math.cos(b) * 0.6).multiplyScalar(2 + r() * 5)); }
    const bg = new THREE.BufferGeometry(); bg.setAttribute("position", new THREE.BufferAttribute(bp, 3));
    const bm = new THREE.PointsMaterial({ color: 0xbae6fd, size: 0.09, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending });
    scene.add(new THREE.Points(bg, bm));
    const LOCK = T0 + 0.6 + (L.length - 1) * 0.07;
    return function (t) {
      L.forEach((l, i) => {
        const k = inOut(win(t, T0 + i * 0.07, 0.6)), u = l.userData;
        l.position.copy(u.from).lerp(u.home, k);
        l.rotation.set(u.rot.x * (1 - k), u.rot.y * (1 - k), u.rot.z * (1 - k));
        l.scale.setScalar(Math.max(0.001, 0.4 + 0.6 * k));
      });
      W3.position.y = END ? -0.4 : 0;
      W3.rotation.y = Math.sin(t * 0.7) * 0.12 * ease(win(t, LOCK, 0.6));
      const s = win(t, LOCK, 1.0);
      sweep.position.set(-4 + s * 8, 0.6 + W3.position.y, 2.2); sweep.intensity = s > 0 && s < 1 ? 5 * Math.sin(s * Math.PI) : 0;
      const b = win(t, LOCK - 0.05, 0.9);
      burst.scale.setScalar(1 + b * 14); burst.material.opacity = b > 0 && b < 1 ? (1 - b) * 0.9 : 0;
      for (let i = 0; i < NB; i++) { const p = dirs[i].clone().multiplyScalar(ease(b)); bp[i * 3] = p.x; bp[i * 3 + 1] = p.y + W3.position.y; bp[i * 3 + 2] = p.z; }
      bg.attributes.position.needsUpdate = true; bm.opacity = b > 0 && b < 1 ? 1 - b : 0;
      animMark(M, t, END ? 0 : LOCK - 0.25);
      st.rotation.y = t * 0.03;
      const z = (END ? 15 : 16.5) - ease(win(t, 0, 3.5)) * 1.6;
      camera.position.set(Math.sin(t * 0.08) * 0.8, 0.3, z); camera.lookAt(0, END ? 0.6 : 0, 0);
      renderer.render(scene, camera);
    };
  }

  // ── phone with a live Enoryx dashboard drawn on a canvas texture ─────────
  function phone(scene, w, h) {
    const g = new THREE.Group(); scene.add(g);
    const shape = new THREE.Shape(); const rr = 0.36, x = -w / 2, y = -h / 2;
    shape.moveTo(x + rr, y); shape.lineTo(x + w - rr, y); shape.quadraticCurveTo(x + w, y, x + w, y + rr); shape.lineTo(x + w, y + h - rr); shape.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
    shape.lineTo(x + rr, y + h); shape.quadraticCurveTo(x, y + h, x, y + h - rr); shape.lineTo(x, y + rr); shape.quadraticCurveTo(x, y, x + rr, y);
    const body = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.22, bevelEnabled: true, bevelSize: 0.05, bevelThickness: 0.05, bevelSegments: 3 }), new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.7, roughness: 0.25 }));
    body.position.z = -0.22; g.add(body);
    const cv = document.createElement("canvas"); cv.width = 512; cv.height = 1024;
    const tex = new THREE.CanvasTexture(cv); tex.encoding = THREE.sRGBEncoding;
    const scr = new THREE.Mesh(new THREE.PlaneGeometry(w - 0.2, h - 0.24), new THREE.MeshBasicMaterial({ map: tex })); scr.position.z = 0.06; g.add(scr);
    return { g, cv, tex };
  }
  const ROWS = [["Climatisation", "4,2 kW"], ["Groupe électrogène", "arrêt"], ["Chambre froide", "-18 °C"], ["Compteur général", "12,6 kW"]];
  function drawDash(P, t, o) {
    const c = P.cv.getContext("2d"), W = 512, H = 1024;
    const alertK = o.alert == null ? 0 : ease(win(t, o.alert, 0.3)), bad = o.bad == null ? 0 : ease(win(t, o.bad, 0.3));
    c.fillStyle = "#07122a"; c.fillRect(0, 0, W, H);
    c.fillStyle = "#38bdf8"; c.font = "800 34px Inter, sans-serif"; c.fillText("ENORYX", 40, 92);
    c.fillStyle = "#16a34a"; c.beginPath(); c.arc(W - 60, 80, 10, 0, Math.PI * 2); c.fill();
    c.fillStyle = "#94a3b8"; c.font = "500 22px Inter, sans-serif"; c.fillText("EN DIRECT", W - 190, 88);
    c.fillStyle = "#94a3b8"; c.font = "600 24px Inter, sans-serif"; c.fillText("Consommation", 40, 170);
    const kw = 12.6 + 0.4 * Math.sin(t * 2.1) + 3.1 * bad;
    c.fillStyle = bad > 0.5 ? "#ea580c" : "#f8fafc"; c.font = "900 84px Inter, sans-serif"; c.fillText(kw.toFixed(1).replace(".", ",") + " kW", 40, 262);
    // chart
    const cx = 40, cy = 300, cw = W - 80, ch = 230;
    c.fillStyle = "#0c1730"; c.fillRect(cx, cy, cw, ch);
    const draw = clamp(o.draw == null ? 1 : win(t, o.draw, 1.2));
    const N = 60; c.lineWidth = 6; c.lineJoin = "round";
    c.strokeStyle = "#38bdf8"; c.beginPath();
    for (let i = 0; i <= N * draw; i++) {
      const u = i / N, spike = bad * (u > 0.7 ? Math.sin((u - 0.7) / 0.3 * Math.PI * 0.5) * 0.45 : 0);
      const yy = cy + ch * (0.7 - 0.3 * Math.sin(u * 5 + t * 1.3) * 0.5 - 0.15 * Math.sin(u * 13 + t * 2) - spike);
      if (i === 0) c.moveTo(cx + u * cw, yy); else c.lineTo(cx + u * cw, yy);
      if (bad > 0.5 && i === Math.floor(N * 0.7)) { c.stroke(); c.strokeStyle = "#ea580c"; c.beginPath(); c.moveTo(cx + u * cw, yy); }
    }
    c.stroke();
    // equipment rows
    ROWS.forEach(([n, v], i) => {
      const y0 = 580 + i * 98, isBad = i === 0 && bad > 0.5;
      c.fillStyle = isBad ? "#3b1607" : "#0c1730"; c.fillRect(40, y0, W - 80, 80);
      c.fillStyle = isBad ? "#ea580c" : (i === 1 ? "#64748b" : "#16a34a"); c.beginPath(); c.arc(76, y0 + 40, 12, 0, Math.PI * 2); c.fill();
      c.fillStyle = "#f8fafc"; c.font = "700 26px Inter, sans-serif"; c.fillText(n, 104, y0 + 49);
      c.fillStyle = isBad ? "#ea580c" : "#94a3b8"; c.font = "700 24px Inter, sans-serif"; c.textAlign = "right"; c.fillText(isBad ? "+38 %" : v, W - 60, y0 + 49); c.textAlign = "left";
    });
    if (alertK > 0) {
      const y = -140 + alertK * 160;
      c.fillStyle = "#ea580c"; c.fillRect(24, y, W - 48, 120);
      c.fillStyle = "#ffffff"; c.font = "800 30px Inter, sans-serif"; c.fillText("Dérive détectée", 48, y + 52);
      c.font = "600 22px Inter, sans-serif"; c.fillText("Climatisation · salle 3", 48, y + 92);
    }
    P.tex.needsUpdate = true;
  }

  // ── 4 & 5 · phone + equipment anchors linked by data lines ───────────────
  // pins: HTML cards pinned to the 4 anchors; o.alert / o.bad switch the clim to drift mode.
  function live(canvas, pins, o = {}) {
    const { renderer, scene, camera, project } = base(canvas, 38);
    scene.fog = null;
    grid(scene, 40, 40, -5.2, 0x13213f, 0.45);
    stars(scene, 300, 31, 30);
    const P = phone(scene, 2.5, 5.0);
    const halo = glow(C.cyan, 9); halo.position.z = -1.2; halo.material.opacity = 0.35; scene.add(halo);
    const AN = [V(-1.85, 2.9, 1.3), V(1.85, 1.35, 1.6), V(-1.85, -0.55, 1.5), V(1.85, -2.3, 1.2)];
    const nodes = AN.map((p, i) => { const s = glow(i === 0 && o.bad != null ? C.orange : C.cyan, 0.9); s.position.copy(p); scene.add(s); return s; });
    const lines = AN.map((p) => {
      const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints([p, V(p.x * 0.25, p.y * 0.6, 0.15)]), new THREE.LineDashedMaterial({ color: C.cyan, dashSize: 0.16, gapSize: 0.1, transparent: true, opacity: 0 }));
      l.computeLineDistances(); scene.add(l); return l;
    });
    const packets = AN.map(() => { const s = glow(0xbae6fd, 0.45); scene.add(s); return s; });
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.5, 0.6, 64), new THREE.MeshBasicMaterial({ color: C.orange, transparent: true, opacity: 0, side: THREE.DoubleSide }));
    ring.position.copy(AN[0]); scene.add(ring);
    const AT = o.at || [0.15, 0.35, 0.55, 0.75];
    return function (t) {
      drawDash(P, t, o);
      const intro = o.rise ? ease(win(t, 0, 0.7)) : 1;
      P.g.position.y = -0.2 - (1 - intro) * 6;
      P.g.rotation.y = -0.22 + Math.sin(t * 0.6) * 0.1; P.g.rotation.x = -0.05;
      const bad = o.bad == null ? 0 : ease(win(t, o.bad, 0.3));
      AN.forEach((p, i) => {
        const k = ease(win(t, AT[i], 0.4));
        lines[i].material.opacity = 0.7 * k; lines[i].material.color.set(i === 0 && bad > 0.5 ? C.orange : C.cyan);
        nodes[i].material.opacity = k * (i === 0 && bad > 0.5 ? 0.7 + 0.3 * Math.sin(t * 10) : 0.8);
        const ph = (t - AT[i] - 0.3 - i * 0.17) / 0.9, on = ph > 0, f = on ? ph % 1 : 0;
        packets[i].position.copy(p).lerp(V(p.x * 0.25, p.y * 0.6, 0.15), f); packets[i].material.opacity = on ? Math.sin(f * Math.PI) : 0;
      });
      if (o.bad != null) { const ph = ((t - o.bad) % 0.9 + 0.9) % 0.9 / 0.9; ring.scale.setScalar(1 + ph * 2.2); ring.material.opacity = bad * (1 - ph); ring.lookAt(camera.position); }
      const push = o.push == null ? 0 : inOut(win(t, o.push, 1.4));
      camera.position.set(Math.sin(t * 0.09) * 1.2, 0.4, 17.5 - push * 3.2); camera.lookAt(push * -0.2, 0.15, 0);
      renderer.render(scene, camera);
      AN.forEach((p, i) => pin(pins[i], project, p, 0, 0));
      if (pins[4]) { P.g.updateMatrixWorld(); pin(pins[4], project, V(0, 2.35, 0.1).applyMatrix4(P.g.matrixWorld), 0, 0); }
    };
  }

  // ── 6 · gains: two orange/red columns drop, the green one rises ──────────
  function gains(canvas, pins, o = {}) {
    const AT = o.at || [0.1, 1.0, 1.8];
    const { renderer, scene, camera, project } = base(canvas, 38);
    scene.fog = null;
    stars(scene, 260, 41, 30);
    const plat = new THREE.Mesh(new THREE.CylinderGeometry(4.6, 4.8, 0.3, 96), new THREE.MeshStandardMaterial({ color: 0x0c1730, metalness: 0.5, roughness: 0.4, emissive: 0x0b2a55, emissiveIntensity: 0.4 }));
    plat.position.y = -0.15; scene.add(plat);
    const edge = new THREE.Mesh(new THREE.TorusGeometry(4.7, 0.04, 12, 160), new THREE.MeshBasicMaterial({ color: C.cyan })); edge.rotation.x = Math.PI / 2; scene.add(edge);
    const spec = [{ x: -2.6, c: C.orange, a: 4.6, b: 1.3 }, { x: 0, c: RED, a: 3.8, b: 0.9 }, { x: 2.6, c: C.green, a: 0.8, b: 4.4 }];
    const cols = spec.map((s) => {
      const m = new THREE.Mesh(new THREE.BoxGeometry(1.5, 1, 1.5), new THREE.MeshStandardMaterial({ color: s.c, emissive: s.c, emissiveIntensity: 0.45, metalness: 0.2, roughness: 0.35, transparent: true, opacity: 0.92 }));
      m.position.x = s.x; scene.add(m);
      const cap = glow(s.c, 2.6); scene.add(cap); return { m, cap, s };
    });
    const r = rng(77), coins = [];
    for (let i = 0; i < 12; i++) { const c = coin(0.26); c.userData = { ph: r(), dx: (r() - 0.5) * 1.6, rx: r() * 6 }; scene.add(c); coins.push(c); }
    const tops = spec.map(() => V(0, 0, 0));
    return function (t) {
      cols.forEach(({ m, cap, s }, i) => {
        const born = ease(win(t, 0, 0.4)), k = inOut(win(t, AT[i] + 0.15, 0.8));
        const h = Math.max(0.001, (s.a + (s.b - s.a) * k) * born);
        m.scale.y = h; m.position.y = h / 2;
        cap.position.set(s.x, h + 0.1, 0); cap.material.opacity = 0.5 * born;
        tops[i].set(s.x, h, 0.75);
      });
      const g = win(t, AT[2] + 0.6, 2.4);
      coins.forEach((c) => { const u = c.userData, life = g > 0 ? ((t - AT[2] - 0.6) * 0.8 + u.ph) % 1 : 0; c.visible = g > 0; c.position.set(2.6 + u.dx * life, tops[2].y + 0.4 + life * 3.2, 0.3); c.rotation.set(u.rx + t * 4, t * 3, 0); c.scale.setScalar(Math.max(0.001, Math.sin(life * Math.PI))); });
      const a = -0.35 + t * 0.07;
      camera.position.set(Math.sin(a) * 19, 6.2, Math.cos(a) * 19); camera.lookAt(0, 2.6, 0);
      renderer.render(scene, camera);
      cols.forEach((c, i) => pin(pins[i], project, V(spec[i].x, 0, 0.9), 0, 26));
    };
  }

  Object.assign(window.ENX3D, { meter, brand, live, gains });
})();
