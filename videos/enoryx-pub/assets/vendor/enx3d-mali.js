/* Enoryx Mali — extra 3D builders (blackout, AC at night, breakdown, results, district).
 * Same contract as enx3d.js: builder(canvas, …) → render(t), pure function of t. */
(function () {
  const { C, clamp, ease, inOut, back, win, rng, base, glow, pin, grid } = window.ENX3D._;

  // a tower with a window grid on the two visible faces
  function tower(scene, o) {
    const g = new THREE.Group(); g.position.set(o.x || 0, 0, o.z || 0); scene.add(g);
    const body = new THREE.Mesh(new THREE.BoxGeometry(o.w, o.h, o.d), new THREE.MeshStandardMaterial({ color: o.color || 0x0d1a38, roughness: 0.55, metalness: 0.2 }));
    body.position.y = o.h / 2; g.add(body);
    const roof = new THREE.Mesh(new THREE.BoxGeometry(o.w + 0.2, 0.22, o.d + 0.2), new THREE.MeshStandardMaterial({ color: 0x1e2a44 }));
    roof.position.y = o.h + 0.11; g.add(roof);
    const wins = [], geo = new THREE.PlaneGeometry(0.5, 0.46), r = rng(o.seed || 5);
    const rows = Math.floor((o.h - 1) / 0.74), cf = Math.floor(o.w / 0.8), cs = Math.floor(o.d / 0.8);
    for (let f = 0; f < 2; f++) for (let row = 0; row < rows; row++) for (let col = 0; col < (f ? cs : cf); col++) {
      const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: 0x0f1d3c }));
      const y = 0.9 + row * 0.74;
      if (!f) m.position.set(-o.w / 2 + 0.4 + col * 0.8 + (o.w - cf * 0.8) / 2, y, o.d / 2 + 0.01);
      else { m.position.set(o.w / 2 + 0.01, y, -o.d / 2 + 0.4 + col * 0.8 + (o.d - cs * 0.8) / 2); m.rotation.y = Math.PI / 2; }
      m.userData = { k: r(), f }; g.add(m); wins.push(m);
    }
    return { g, body, wins };
  }
  function ground(scene) {
    grid(scene, 80, 40, 0, 0x13213f, 0.6);
    const gnd = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.MeshStandardMaterial({ color: 0x060d1f, roughness: 1 }));
    gnd.rotation.x = -Math.PI / 2; gnd.position.y = -0.01; scene.add(gnd);
  }
  function smoke(scene, n, seed, color, size) {
    const pos = new Float32Array(n * 3), r = rng(seed), seeds = [];
    for (let i = 0; i < n; i++) seeds.push([r() - 0.5, r() - 0.5, r(), 0.5 + r() * 0.7]);
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const tex = glow(0xffffff, 1).material.map;
    const m = new THREE.PointsMaterial({ color, size: size * 3.2, map: tex, transparent: true, opacity: 0, depthWrite: false });
    scene.add(new THREE.Points(g, m));
    return { m, step(t, ox, oy, oz, rise, spread) {
      for (let i = 0; i < n; i++) { const [x, z, ph, sp] = seeds[i]; const life = (t * sp * 0.5 + ph) % 1;
        pos[i * 3] = ox + x * spread * (0.3 + life) + Math.sin(life * 7 + ph * 9) * 0.2; pos[i * 3 + 1] = oy + life * rise; pos[i * 3 + 2] = oz + z * spread * (0.3 + life); }
      g.attributes.position.needsUpdate = true; } };
  }
  // generator: a boxy genset with exhaust
  function genset(scene, x, z) {
    const g = new THREE.Group(); g.position.set(x, 0, z); scene.add(g);
    const body = new THREE.Mesh(new THREE.BoxGeometry(2.6, 1.5, 1.4), new THREE.MeshStandardMaterial({ color: 0x1b6b3a, roughness: 0.5, metalness: 0.3 }));
    body.position.y = 0.75; g.add(body);
    const grille = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 0.9), new THREE.MeshStandardMaterial({ color: 0x0b2416 }));
    grille.position.set(0.6, 0.8, 0.71); g.add(grille);
    const pipe = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.9, 16), new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.6 }));
    pipe.position.set(-0.9, 1.9, 0); g.add(pipe);
    const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 16), new THREE.MeshBasicMaterial({ color: 0x334155 }));
    lamp.position.set(-0.6, 1.1, 0.72); g.add(lamp);
    return { g, lamp, pipeTop: new THREE.Vector3(x - 0.9, 2.4, z) };
  }
  // wall AC unit with a spinning fan
  function acUnit(parent, x, y, z, ry = 0, s = 1) {
    const g = new THREE.Group(); g.position.set(x, y, z); g.rotation.y = ry; g.scale.setScalar(s); parent.add(g);
    const box = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.7, 0.45), new THREE.MeshStandardMaterial({ color: 0xcbd5e1, roughness: 0.4, metalness: 0.2 }));
    g.add(box);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.24, 0.03, 8, 32), new THREE.MeshStandardMaterial({ color: 0x64748b }));
    ring.position.set(0.15, 0, 0.23); g.add(ring);
    const fan = new THREE.Group(); fan.position.set(0.15, 0, 0.24); g.add(fan);
    for (let b = 0; b < 3; b++) { const bl = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.4, 0.02), new THREE.MeshStandardMaterial({ color: 0x334155 })); bl.rotation.z = b * Math.PI * 2 / 3; fan.add(bl); }
    const led = new THREE.Mesh(new THREE.SphereGeometry(0.04, 12, 12), new THREE.MeshBasicMaterial({ color: C.cyan })); led.position.set(-0.35, 0.2, 0.23); g.add(led);
    return { g, fan, led, box };
  }

  // ── 1 · electricity is expensive; blackout → generator burns diesel ──────
  function blackout(canvas, labels) {
    const { renderer, scene, camera, project } = base(canvas, 40);
    ground(scene);
    const r = rng(9);
    for (let i = 0; i < 10; i++) { const h = 2 + r() * 4, w = 1.6 + r() * 1.4; const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, w), new THREE.MeshStandardMaterial({ color: 0x07102a, roughness: 0.9 }));
      const a = Math.PI * (1.05 + r() * 0.9), d = 10 + r() * 10; m.position.set(Math.cos(a) * d, h / 2, Math.sin(a) * d - 5); scene.add(m); }
    const T = tower(scene, { w: 4.2, h: 8.2, d: 3.4, seed: 3 });
    const G = genset(scene, 4.4, 2.6);
    const sm = smoke(scene, 160, 4, 0x9aa3b2, 0.22);
    const lit = new THREE.Color(0xf5d68a), dim = new THREE.Color(0x0f1d3c), litB = new THREE.Color(0xbfdcff);
    const cut = 3.25, genOn = 4.3;
    const flash = new THREE.PointLight(0xfff1c7, 0, 18); flash.position.set(0, 6, 5); scene.add(flash);
    return function (t) {
      const on = ease(win(t, 0.1, 0.8)), off = ease(win(t, cut, 0.25)), back2 = ease(win(t, genOn + 0.3, 0.8));
      T.wins.forEach((m) => {
        const k = m.userData.k; const base1 = on * (k < 0.78 ? 1 : 0);
        const flick = t > cut - 0.35 && t < cut ? (Math.sin(t * 80 + k * 30) > 0 ? 1 : 0.2) : 1;
        const after = back2 * (k < 0.35 ? 0.8 : 0);   // generator powers only part of the building
        const v = base1 * flick * (1 - off) + after;
        m.material.color.copy(dim).lerp(k > 0.5 ? lit : litB, clamp(v));
      });
      flash.intensity = 1.2 * on * (1 - off) + 0.5 * back2;
      G.g.scale.setScalar(Math.max(0.001, back(win(t, genOn - 0.4, 0.5), 1.6)));
      const run = t > genOn ? 1 : 0;
      G.g.position.y = run ? Math.sin(t * 60) * 0.015 : 0;
      G.lamp.material.color.set(run ? C.green : 0x334155);
      sm.step(t, G.pipeTop.x, G.pipeTop.y, G.pipeTop.z, 4.5, 1.2);
      sm.m.opacity = 0.75 * ease(win(t, genOn + 0.2, 0.8)) * (1 + 0.35 * ease(win(t, 5.4, 0.5)));
      const a = 0.55 + t * 0.04, d = 20 - ease(win(t, 0, 7)) * 2;
      camera.position.set(Math.sin(a) * d, 4.8 + t * 0.08, Math.cos(a) * d);
      camera.lookAt(1.2, 4.3, 0);
      renderer.render(scene, camera);
      pin(labels[0], project, new THREE.Vector3(4.4, 2.0, 2.6), 0, -20);
    };
  }

  // ── 2 · ACs running at night in empty rooms ──────────────────────────────
  function acNight(canvas, labels) {
    const { renderer, scene, camera, project } = base(canvas, 40);
    ground(scene);
    const blds = [
      tower(scene, { x: -3.2, z: -1, w: 3.2, h: 6.6, d: 3, seed: 11 }),
      tower(scene, { x: 1.0, z: 1.2, w: 3.4, h: 9.0, d: 3, seed: 12, color: 0x0f1c3c }),
      tower(scene, { x: 4.6, z: -1.6, w: 2.8, h: 5.2, d: 2.8, seed: 13 }),
    ];
    const acs = [];
    blds.forEach((b, bi) => {
      const h = [6.6, 9, 5.2][bi], w = [3.2, 3.4, 2.8][bi], d = [3, 3, 2.8][bi];
      for (let i = 0; i < Math.floor(h / 1.6); i++) acs.push({ u: acUnit(b.g, w / 2 + 0.28, 1.2 + i * 1.5, -d / 2 + 0.8 + (i % 2) * 1.1, Math.PI / 2, 0.85), t0: 3.3 + acs.length * 0.06 });
    });
    const cold = glow(0x7dd3fc, 3); scene.add(cold);
    const moon = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 32), new THREE.MeshBasicMaterial({ color: 0xdbe7ff })); moon.position.set(-8, 16, -20); scene.add(moon);
    const mg = glow(0x9fc4ff, 8); mg.position.copy(moon.position); scene.add(mg);
    const pts = [new THREE.Vector3(-3.2, 6.8, -1), new THREE.Vector3(1.0, 9.2, 1.2), new THREE.Vector3(4.6, 5.4, -1.6)];
    return function (t) {
      blds.forEach((b, bi) => b.g.scale.setScalar(Math.max(0.001, ease(win(t, [1.05, 1.4, 2.25][bi] - 0.2, 0.6)))));
      blds.forEach((b) => b.wins.forEach((m) => m.material.color.set(0x0f1d3c)));   // rooms are empty: windows dark
      acs.forEach(({ u, t0 }) => {
        const on = ease(win(t, t0, 0.4));
        u.fan.rotation.z = on * (t - t0) * 18;
        u.led.material.color.set(on > 0.5 ? C.cyan : 0x1e293b);
      });
      const night = ease(win(t, 4.4, 0.8));
      mg.material.opacity = 0.4 + 0.5 * night;
      cold.position.set(5.6, 3, 0); cold.material.opacity = 0.6 * ease(win(t, 3.4, 0.6));
      const a = 0.6 + t * 0.05, d = 29 - ease(win(t, 0, 6.5)) * 2;
      camera.position.set(Math.sin(a) * d, 6, Math.cos(a) * d);
      camera.lookAt(0.8, 3.6, 0);
      renderer.render(scene, camera);
      labels.forEach((el, i) => pin(el, project, pts[i], 0, -24));
    };
  }

  // ── 3 · breakdown: one AC dies, nobody notices ───────────────────────────
  function breakdown(canvas) {
    const { renderer, scene, camera } = base(canvas, 36);
    grid(scene, 30, 30, -1.4, 0x13213f, 0.5);
    const wall = new THREE.Mesh(new THREE.BoxGeometry(9, 9, 0.3), new THREE.MeshStandardMaterial({ color: 0x0d1a38, roughness: 0.8 }));
    wall.position.set(0, 2.6, -0.5); scene.add(wall);
    const U = acUnit(scene, 0, 1.6, 0, 0, 3.4);
    const warn = new THREE.PointLight(0xdc2626, 0, 12); warn.position.set(0, 2.4, 3); scene.add(warn);
    const rg = glow(0xdc2626, 7); rg.position.set(0, 1.6, 1.2); scene.add(rg);
    const sm = smoke(scene, 140, 21, 0x6b7280, 0.28);
    const FAIL = 2.4;
    return function (t) {
      // fan slows to a stop after the failure (integrated angle, still a pure function of t)
      const spin = t < FAIL ? t * 14 : FAIL * 14 + (1 - Math.exp(-(t - FAIL) * 1.6)) / 1.6 * 14;
      U.fan.rotation.z = spin;
      const f = ease(win(t, FAIL, 0.3));
      U.led.material.color.set(f > 0.5 ? (Math.sin(t * 12) > 0 ? 0xdc2626 : 0x450a0a) : C.cyan);
      warn.intensity = f * (0.55 + 0.25 * Math.sin(t * 6));
      rg.material.opacity = 0.4 * f * (0.7 + 0.3 * Math.sin(t * 6));
      sm.step(t, 1.2, 2.6, 0.4, 3.5, 1.4); sm.m.opacity = 0.55 * ease(win(t, FAIL + 0.3, 0.8));
      U.g.position.x = t > FAIL && t < FAIL + 0.6 ? Math.sin(t * 90) * 0.03 : 0;
      const a = -0.35 + t * 0.045;
      camera.position.set(Math.sin(a) * 13, 3.6 - t * 0.06, Math.cos(a) * 13);
      camera.lookAt(0, 0.4, 0);
      renderer.render(scene, camera);
    };
  }

  // ── 7 · results: three tokens rise (less waste, fewer breakdowns, better upkeep) ──
  function results(canvas, labels, at) {
    const { renderer, scene, camera, project } = base(canvas, 38);
    grid(scene, 30, 30, -3.5, 0x13213f, 0.5);
    const cols = [C.cyan, C.green, 0x60a5fa];
    const tokens = cols.map((c, i) => {
      const g = new THREE.Group(); g.position.set(-1.7, 2.4 - i * 2.9, 0); scene.add(g);
      const disc = new THREE.Mesh(new THREE.CylinderGeometry(1.15, 1.15, 0.3, 64), new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 0.35, roughness: 0.3, metalness: 0.4 }));
      disc.rotation.x = Math.PI / 2; g.add(disc);
      const rim = new THREE.Mesh(new THREE.TorusGeometry(1.15, 0.07, 12, 64), new THREE.MeshStandardMaterial({ color: 0xe2e8f0, metalness: 0.7, roughness: 0.2 })); g.add(rim);
      const hg = glow(c, 4); hg.position.z = -0.4; g.add(hg);
      return { g, hg };
    });
    return function (t) {
      tokens.forEach(({ g, hg }, i) => {
        const k = back(win(t, at[i], 0.6), 1.5);
        g.scale.setScalar(Math.max(0.001, k)); g.rotation.y = (1 - ease(win(t, at[i], 1.2))) * Math.PI * 2 + Math.sin(t * 1.2 + i) * 0.25;
        hg.material.opacity = 0.5 * ease(win(t, at[i], 0.6));
      });
      camera.position.set(Math.sin(t * 0.08) * 1.5, 0.6, 18);
      camera.lookAt(0, 0.4, 0);
      renderer.render(scene, camera);
      labels.forEach((el, i) => pin(el, project, new THREE.Vector3(-0.3, 2.4 - i * 2.9, 0), 0, 0));
    };
  }

  // ── 8 · district: five building types on a turntable ─────────────────────
  function district(canvas, labels, at) {
    const { renderer, scene, camera, project } = base(canvas, 38);
    grid(scene, 40, 40, 0, 0x13213f, 0.5);
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(6.4, 6.6, 0.3, 96), new THREE.MeshStandardMaterial({ color: 0x0c1730, roughness: 0.6 }));
    disc.position.y = 0.15; scene.add(disc);
    const turn = new THREE.Group(); scene.add(turn);
    const std = (c) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.5, metalness: 0.15 });
    const make = [
      () => { const g = new THREE.Group(); const b = new THREE.Mesh(new THREE.BoxGeometry(1.6, 4.6, 1.6), std(0x1d4ed8)); b.position.y = 2.3; g.add(b); return [g, 4.9]; },                       // bureaux
      () => { const g = new THREE.Group(); const b = new THREE.Mesh(new THREE.BoxGeometry(2.6, 3.0, 1.4), std(0x0e7490)); b.position.y = 1.5; g.add(b);
              const s = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.5, 0.1), new THREE.MeshBasicMaterial({ color: C.cyan })); s.position.set(0, 3.3, 0); g.add(s); return [g, 3.8]; },             // hôtel
      () => { const g = new THREE.Group(); const b = new THREE.Mesh(new THREE.BoxGeometry(2.4, 2.4, 1.8), std(0xe2e8f0)); b.position.y = 1.2; g.add(b);
              const c1 = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.28, 0.1), new THREE.MeshBasicMaterial({ color: 0xdc2626 })); c1.position.set(0, 1.6, 0.92); g.add(c1);
              const c2 = c1.clone(); c2.rotation.z = Math.PI / 2; g.add(c2); return [g, 2.9]; },                                                                                                  // hôpital
      () => { const g = new THREE.Group(); const b = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.3, 1.6), std(0xcbd5e1)); b.position.y = 0.15; g.add(b);
              for (let i = 0; i < 4; i++) { const c = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 1.6, 16), std(0xe2e8f0)); c.position.set(-0.9 + i * 0.6, 1.1, 0.5); g.add(c); }
              const r = new THREE.Mesh(new THREE.ConeGeometry(1.6, 0.8, 4), std(0xcbd5e1)); r.rotation.y = Math.PI / 4; r.scale.set(1, 1, 0.65); r.position.y = 2.3; g.add(r); return [g, 3.0]; },   // banque
      () => { const g = new THREE.Group(); const b = new THREE.Mesh(new THREE.BoxGeometry(3.0, 1.6, 2.0), std(0x15803d)); b.position.y = 0.8; g.add(b);
              const s = new THREE.Mesh(new THREE.BoxGeometry(2.2, 0.35, 0.1), new THREE.MeshBasicMaterial({ color: 0xfacc15 })); s.position.set(0, 1.85, 1.0); g.add(s); return [g, 2.4]; },      // supermarché
    ];
    const items = make.map((f, i) => { const [g, top] = f(); const a = i / 5 * Math.PI * 2; g.position.set(Math.sin(a) * 4.2, 0.3, Math.cos(a) * 4.2); g.rotation.y = a; turn.add(g); return { g, top }; });
    const M = window.ENX3D._.mark(0.5); M.g.position.y = 6.2; scene.add(M.g);
    const tmp = new THREE.Vector3();
    return function (t) {
      turn.rotation.y = -0.3 + t * 0.32;
      items.forEach(({ g }, i) => g.scale.setScalar(Math.max(0.001, back(win(t, at[i], 0.5), 1.6))));
      window.ENX3D._.animMark(M, t, at[5] || 2.6);
      camera.position.set(0, 13, 30); camera.lookAt(0, 2.8, 0);
      renderer.render(scene, camera);
      items.forEach(({ g, top }, i) => { g.getWorldPosition(tmp); tmp.y += top; const q = project(tmp); pin(labels[i], project, tmp, 0, -10 - (i % 2) * 58); labels[i].style.opacity = q.z < 1 && tmp.z > -3 ? 1 : 0; });
    };
  }

  Object.assign(window.ENX3D, { blackout, acNight, breakdown, results, district });
})();
