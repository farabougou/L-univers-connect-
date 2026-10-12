/* « Boucle infinie de la flèche » — Bamako.
 * One Three.js scene, four shots, render(t) is a pure function of t (0..DUR) so every frame is seek-safe.
 *   A 0.0–2.4  the man at his desk: the arrow lies on the notebook, lifts off and shoots out
 *   B 2.4–7.0  the arrow flies across Bamako to the building and dives into a window
 *   C 7.0–9.6  through a lit corridor toward a bright opening
 *   D 9.6–12.0 back in the man's office: the arrow lands on the notebook = first frame (loop)
 */
(function () {
  const W = 1080, H = 1920, DUR = 12.0;
  const CUT_B = 2.4, CUT_C = 7.0, CUT_D = 9.6;
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const win = (t, a, d) => clamp((t - a) / d);
  const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);
  const inOut = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  const lerp = (a, b, k) => a + (b - a) * k;
  function rng(s) { return () => { s |= 0; s = (s + 0x6d2b79f5) | 0; let r = Math.imul(s ^ (s >>> 15), 1 | s); r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r; return ((r ^ (r >>> 14)) >>> 0) / 4294967296; }; }
  const V = (x, y, z) => new THREE.Vector3(x, y, z);

  function build(canvas) {
    if (THREE.ColorManagement) THREE.ColorManagement.legacyMode = false;
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1); renderer.setSize(W, H, false); renderer.outputEncoding = THREE.sRGBEncoding;
    const camera = new THREE.PerspectiveCamera(40, W / H, 0.02, 400);
    const scenes = { A: new THREE.Scene(), B: new THREE.Scene(), C: new THREE.Scene() };
    Object.values(scenes).forEach((s) => { s.add(new THREE.HemisphereLight(0xfff2e0, 0x3a2a1c, 1.0)); const k = new THREE.DirectionalLight(0xffffff, 1.1); k.position.set(4, 8, 10); s.add(k); });
    scenes.C.background = new THREE.Color(0x120c08);

    // ── photos (wait for them before the first render) ──────────────────────
    window.__hf = window.__hf || {}; window.__hf.buildReady = window.__hf.buildReady || {};
    const loader = new THREE.TextureLoader();
    const tex = (url) => new Promise((res) => { const t = loader.load(url, () => res(t), undefined, () => res(t)); t.encoding = THREE.sRGBEncoding; });
    let manMat = new THREE.MeshBasicMaterial({ color: 0x222222 }), bldMat = new THREE.MeshBasicMaterial({ color: 0x222222 });
    window.__hf.buildReady["fleche-photos"] = Promise.all([tex("assets/homme.png"), tex("assets/batiment.jpg")]).then(([m, b]) => {
      manMat.map = m; manMat.color.set(0xffffff); manMat.needsUpdate = true;
      bldMat.map = b; bldMat.color.set(0xffffff); bldMat.needsUpdate = true;
    });
    // man photo 1122×1402 → 8 × 10 world units; notebook at u .463, v .856
    const man = new THREE.Mesh(new THREE.PlaneGeometry(8, 10), manMat); scenes.A.add(man);
    const NOTE = V(-0.3, -3.5, 0.06);
    // building photo 1280×960 → 24 × 18; target window at px (440, 262)
    const bld = new THREE.Mesh(new THREE.PlaneGeometry(24, 18), bldMat); scenes.B.add(bld);
    const WIN = V((440 / 1280 - 0.5) * 24, (0.5 - 262 / 960) * 18, 0.02);

    // dust motes for depth in the photo shots
    const dust = (scene, seed, n, spread, z0, z1, color) => {
      const r = rng(seed), p = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) { p[i * 3] = (r() - 0.5) * spread; p[i * 3 + 1] = (r() - 0.5) * spread * 1.6; p[i * 3 + 2] = lerp(z0, z1, r()); }
      const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(p, 3));
      const pts = new THREE.Points(g, new THREE.PointsMaterial({ color, size: 0.03, transparent: true, opacity: 0.55, depthWrite: false }));
      scene.add(pts); return pts;
    };
    const dustA = dust(scenes.A, 3, 220, 8, 1, 11, 0xffe2b8);
    const dustB = dust(scenes.B, 9, 260, 22, 2, 24, 0xfff3d6);

    // ── corridor (shot C) ───────────────────────────────────────────────────
    const C = scenes.C, LEN = 64, Wc = 3.2, Hc = 3.4;
    const sand = new THREE.MeshStandardMaterial({ color: 0xc7a06a, roughness: 0.85 });
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(Wc, LEN), new THREE.MeshStandardMaterial({ color: 0x6b5644, roughness: 0.6, metalness: 0.1 }));
    floor.rotation.x = -Math.PI / 2; floor.position.set(0, 0, -LEN / 2); C.add(floor);
    const ceil = new THREE.Mesh(new THREE.PlaneGeometry(Wc, LEN), new THREE.MeshStandardMaterial({ color: 0xd9c49a, roughness: 0.9 }));
    ceil.rotation.x = Math.PI / 2; ceil.position.set(0, Hc, -LEN / 2); C.add(ceil);
    [-1, 1].forEach((s) => { const w = new THREE.Mesh(new THREE.PlaneGeometry(LEN, Hc), sand); w.rotation.y = -s * Math.PI / 2; w.position.set(s * Wc / 2, Hc / 2, -LEN / 2); C.add(w); });
    const frameM = new THREE.MeshStandardMaterial({ color: 0x8a6a45, roughness: 0.7 }), lampM = new THREE.MeshBasicMaterial({ color: 0xffe0a8 });
    for (let z = -3; z > -LEN + 4; z -= 4) {
      const top = new THREE.Mesh(new THREE.BoxGeometry(Wc, 0.3, 0.3), frameM); top.position.set(0, Hc - 0.15, z); C.add(top);
      [-1, 1].forEach((s) => { const p = new THREE.Mesh(new THREE.BoxGeometry(0.3, Hc, 0.3), frameM); p.position.set(s * (Wc / 2 - 0.15), Hc / 2, z); C.add(p);
        const door = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 2.2), new THREE.MeshStandardMaterial({ color: 0x4a2f1c })); door.rotation.y = -s * Math.PI / 2; door.position.set(s * (Wc / 2 - 0.01), 1.1, z - 2); C.add(door); });
      const lamp = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.05, 0.6), lampM); lamp.position.set(0, Hc - 0.03, z - 2); C.add(lamp);
      const pl = new THREE.PointLight(0xffc77a, 0.9, 6); pl.position.set(0, Hc - 0.4, z - 2); C.add(pl);
    }
    const exit = new THREE.Mesh(new THREE.PlaneGeometry(Wc, Hc), new THREE.MeshBasicMaterial({ color: 0xfff6e6 })); exit.position.set(0, Hc / 2, -LEN); C.add(exit);

    // ── the arrow ───────────────────────────────────────────────────────────
    function makeArrow() {
      const g = new THREE.Group(); // points along local +z
      const wood = new THREE.MeshStandardMaterial({ color: 0x3b2a1e, roughness: 0.55 });
      const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 2.2, 12), wood); shaft.rotation.x = Math.PI / 2; g.add(shaft);
      const head = new THREE.Mesh(new THREE.ConeGeometry(0.09, 0.32, 16), new THREE.MeshStandardMaterial({ color: 0x9ca3af, metalness: 0.9, roughness: 0.25 }));
      head.rotation.x = Math.PI / 2; head.position.z = 1.25; g.add(head);
      // striped feathers (canvas texture — shapes only, no text)
      const c = document.createElement("canvas"); c.width = 64; c.height = 256; const x = c.getContext("2d");
      x.fillStyle = "#e9e4dc"; x.fillRect(0, 0, 64, 256);
      for (let i = 0; i < 256; i += 18) { x.fillStyle = "#2b2622"; x.fillRect(0, i, 64, 8); }
      const ft = new THREE.CanvasTexture(c);
      const fm = new THREE.MeshStandardMaterial({ map: ft, side: THREE.DoubleSide, roughness: 0.8 });
      const fs = new THREE.Shape(); fs.moveTo(0, 0); fs.lineTo(0.28, 0.12); fs.quadraticCurveTo(0.34, 0.45, 0.24, 0.72); fs.lineTo(0, 0.62); fs.lineTo(0, 0);
      const fg = new THREE.ShapeGeometry(fs);
      for (let i = 0; i < 3; i++) { const f = new THREE.Mesh(fg, fm); const piv = new THREE.Group(); f.rotation.x = -Math.PI / 2; f.position.z = -0.4; piv.add(f); piv.rotation.z = i * Math.PI * 2 / 3; piv.position.z = -1.05; g.add(piv); }
      const nock = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.08, 12), new THREE.MeshStandardMaterial({ color: 0xb91c1c })); nock.rotation.x = Math.PI / 2; nock.position.z = -1.12; g.add(nock);
      return g;
    }
    const arrows = { A: makeArrow(), B: makeArrow(), C: makeArrow() };
    scenes.A.add(arrows.A); scenes.B.add(arrows.B); scenes.C.add(arrows.C);
    const trail = (scene) => { const s = new THREE.Sprite(new THREE.SpriteMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false })); s.scale.set(0.12, 0.12, 1); scene.add(s); return s; };

    // pose helper: place the arrow on a curve at k, aimed along the tangent
    const tmp = V(0, 0, 0), up = V(0, 1, 0);
    function along(arrow, curve, k, scale) {
      const p = curve.getPoint(clamp(k)), q = curve.getPoint(clamp(k + 0.01));
      arrow.position.copy(p); tmp.copy(q).sub(p);
      if (tmp.lengthSq() < 1e-8) tmp.set(0, 0, -1);
      const m = new THREE.Matrix4().lookAt(V(0, 0, 0), tmp.normalize().multiplyScalar(-1), up); // three looks down -z; arrow points +z
      arrow.quaternion.setFromRotationMatrix(m); arrow.scale.setScalar(scale);
    }
    // the resting pose on the notebook (shared by t=0 and t=12 → seamless loop)
    const restDir = V(0.86, 0.42, 0.08).normalize();
    const restQ = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().lookAt(V(0, 0, 0), restDir.clone().multiplyScalar(-1), V(0, 0, 1)));
    const REST_SCALE = 0.62;

    const pathA = new THREE.CatmullRomCurve3([NOTE.clone(), V(-0.05, -2.9, 0.7), V(0.35, -1.2, 1.6), V(0.85, 1.4, 2.6), V(1.3, 4.6, 3.6), V(1.6, 7.5, 4.4)]);
    const pathB = new THREE.CatmullRomCurve3([V(2.5, -3.5, 27), V(1.2, -0.2, 21), V(-1.4, 2.6, 12), V(-3.3, 3.9, 4), WIN.clone().add(V(0, 0, 0.2))]);
    const pathD = new THREE.CatmullRomCurve3([V(0.8, 2.2, 15.5), V(0.5, 0.2, 9), V(0.1, -2.2, 3.6), V(-0.2, -3.2, 0.9), NOTE.clone()]);

    const camLook = V(0, 0, 0);
    const HOME = { pos: V(0, 0, 13.74), look: V(0, 0, 0) };

    let lastT = 0;
    window.__hf.buildReady["fleche-photos"].then(() => render(lastT));
    function render(t) {
      t = clamp(t, 0, DUR); lastT = t;
      let scene;
      if (t < CUT_B) {
        // ── A: lift-off from the notebook ──
        scene = scenes.A; const a = arrows.A;
        const lift = inOut(win(t, 0.55, 1.75));
        if (t < 0.55) { a.position.copy(NOTE); a.quaternion.copy(restQ); a.scale.setScalar(REST_SCALE + 0.03 * Math.sin(t * 12) * win(t, 0.25, 0.3)); }
        else { along(a, pathA, lift, REST_SCALE + 0.55 * lift); if (lift < 0.12) a.quaternion.slerp(restQ, 1 - lift / 0.12); }
        const push = ease(win(t, 0, 2.4));
        const whip = Math.pow(win(t, 2.0, 0.4), 2);
        camera.position.set(lerp(0, 0.25, push), lerp(0, 0.3, push), lerp(13.74, 11.2, push));
        camLook.set(lerp(0, 0.3, lift), lerp(0, 0.5, lift), 0);
        camera.lookAt(camLook); camera.rotation.z += whip * 0.35;
        dustA.rotation.y = t * 0.02;
      } else if (t < CUT_C) {
        // ── B: across Bamako into a window ──
        scene = scenes.B; const tb = t - CUT_B, a = arrows.B;
        const ck = inOut(win(tb, 0, 4.6));
        const camPath = new THREE.CatmullRomCurve3([V(-0.6, 0.9, 21.5), V(-1.2, 1.9, 16), V(-2.6, 3.3, 10), V(-3.5, 3.95, 5.5), V(WIN.x, WIN.y, 3.4)]);
        const cp = camPath.getPoint(ck);
        camera.position.copy(cp);
        const ak = clamp(ck + 0.07 + 0.06 * (1 - ck)), ap = camPath.getPoint(ak), aq = camPath.getPoint(clamp(ak + 0.02));
        const lead = new THREE.CatmullRomCurve3([ap.clone().add(V(0.3, -0.5, -3.0)), aq.clone().add(V(0.2, -0.35, -3.4)), WIN.clone()]);
        along(a, lead, 0.0, 0.55); if (ak >= 0.995) { a.position.copy(WIN); }
        camLook.set(lerp(-0.7, WIN.x, ease(win(tb, 0.6, 3.6))), lerp(0.9, WIN.y, ease(win(tb, 0.6, 3.6))), 0);
        camera.lookAt(camLook); camera.rotation.z += Math.sin(tb * 1.3) * 0.02 * (1 - ck);
        dustB.position.z = tb * 0.6;
      } else if (t < CUT_D) {
        // ── C: the corridor ──
        scene = scenes.C; const tc = t - CUT_C, a = arrows.C;
        const zc = -LEN * 0.86 * inOut(win(tc, 0, 2.6));
        camera.position.set(Math.sin(tc * 2.2) * 0.12, 1.6 + Math.sin(tc * 3) * 0.05, 2 + zc);
        camera.lookAt(0, 1.65, zc - 10); camera.rotation.z += Math.sin(tc * 1.7) * 0.04;
        a.position.set(Math.sin(tc * 3.1) * 0.18, 1.62 + Math.sin(tc * 4) * 0.08, zc - 2.6 - tc * 0.6);
        a.quaternion.setFromEuler(new THREE.Euler(0.12, Math.PI + 0.42, Math.sin(tc * 5) * 0.3)); a.scale.setScalar(1.15);
      } else {
        // ── D: landing back on the notebook (ends on the exact first frame) ──
        scene = scenes.A; const td = t - CUT_D, a = arrows.A;
        const k = inOut(win(td, 0.0, 2.0));
        along(a, pathD, k, lerp(1.15, REST_SCALE, k));
        if (k > 0.88) a.quaternion.slerp(restQ, (k - 0.88) / 0.12);
        if (td >= 2.0) { a.position.copy(NOTE); a.quaternion.copy(restQ); a.scale.setScalar(REST_SCALE); }
        const back = ease(win(td, 0, 2.3));
        camera.position.set(lerp(0.5, HOME.pos.x, back), lerp(-1.2, HOME.pos.y, back), lerp(6.5, HOME.pos.z, back));
        camLook.set(lerp(0.1, 0, back), lerp(-2.0, 0, back), 0); camera.lookAt(camLook);
        dustA.rotation.y = t * 0.02;
      }
      renderer.render(scene, camera);
    }
    return render;
  }
  window.FLECHE = { build, DUR, CUTS: [CUT_B, CUT_C, CUT_D] };
})();
