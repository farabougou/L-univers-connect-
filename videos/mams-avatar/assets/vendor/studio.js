/* Studio — système de design motion pour HyperFrames (GSAP 3.12).
   Copier dans <projet>/assets/vendor/studio.js (+ studio.css), charger après gsap.min.js.
   Contrat : tout est une fonction pure du temps de la timeline (seek-safe dans les deux sens),
   aucun Math.random / Date.now (hasard = rng(seed)), seulement des transforms et des propriétés de peinture. */
(function () {
  const gsap = window.gsap;
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, p) => a + (b - a) * p;
  function rng(s) { return () => { s |= 0; s = (s + 0x6d2b79f5) | 0; let r = Math.imul(s ^ (s >>> 15), 1 | s); r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r; return ((r ^ (r >>> 14)) >>> 0) / 4294967296; }; }

  // ── 1. Courbes : cubic-bezier exactes (mêmes valeurs qu'After Effects / CSS) et ressort physique ──
  function bezier(x1, y1, x2, y2) {
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const X = (t) => ((ax * t + bx) * t + cx) * t, Y = (t) => ((ay * t + by) * t + cy) * t, dX = (t) => (3 * ax * t + 2 * bx) * t + cx;
    return (p) => {
      if (p <= 0) return 0;
      if (p >= 1) return 1;
      let t = p;
      for (let i = 0; i < 8; i++) { const e = X(t) - p, d = dX(t); if (Math.abs(e) < 1e-7 || Math.abs(d) < 1e-6) break; t -= e / d; }
      if (!(Math.abs(X(t) - p) < 1e-5)) { let a = 0, b = 1; t = p; for (let i = 0; i < 40; i++) { if (X(t) < p) a = t; else b = t; t = (a + b) / 2; } }
      return Y(t);
    };
  }
  // Ressort amorti en forme fermée (pas d'intégrateur, donc seekable). damping 1 = aucun dépassement,
  // 0.8 = dépassement ressenti mais pas vu (iOS), 0.65 = joueur. La durée fait partie de la physique.
  function spring({ response = 0.5, damping = 1 } = {}) {
    const w = (2 * Math.PI) / response, z = damping;
    let pos;
    if (z < 1) { const wd = w * Math.sqrt(1 - z * z); pos = (t) => 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + ((z * w) / wd) * Math.sin(wd * t)); }
    else if (z > 1) { const wo = w * Math.sqrt(z * z - 1); pos = (t) => 1 - Math.exp(-z * w * t) * (Math.cosh(wo * t) + ((z * w) / wo) * Math.sinh(wo * t)); }
    else pos = (t) => 1 - Math.exp(-w * t) * (1 + w * t);
    const rate = z <= 1 ? z * w : (z - Math.sqrt(z * z - 1)) * w, SCAN = 12 / rate, N = 4800;
    let T = SCAN;
    for (let i = N; i >= 0; i--) { const t = (i / N) * SCAN; if (Math.abs(1 - pos(t)) > 0.001) { T = ((i + 1) / N) * SCAN; break; } }
    const xT = pos(T);
    return { duration: T, ease: (p) => pos(p * T) + p * (1 - xT) };
  }
  const ease = {
    silk: bezier(0.16, 1, 0.3, 1),            // arrivée premium : départ franc, très longue décélération
    swift: bezier(0.2, 0.8, 0.2, 1),          // interface (Linear / Stripe) : vif, se pose net
    glide: bezier(0.65, 0, 0.35, 1),          // caméra, morphing, déplacement d'un groupe
    exit: bezier(0.7, 0, 0.84, 0),            // sortie sèche : immobile puis part d'un coup
    accel: bezier(0.45, 0, 0.8, 0.35),        // sortie douce : prend de la vitesse dès le départ
    anticipate: bezier(0.5, -0.35, 0.25, 1),  // recule d'environ 8 % avant de partir
    overshoot: bezier(0.34, 1.35, 0.64, 1),   // dépasse d'environ 6 % puis revient
    breath: (p) => 0.5 - 0.5 * Math.cos(Math.PI * p),
  };
  if (gsap && gsap.registerEase) for (const k in ease) gsap.registerEase('studio-' + k, ease[k]);

  // ── 2. Jetons de temps : durées et décalages. Un groupe doit se lire comme UN temps fort. ──
  const dur = { micro: 0.2, short: 0.4, base: 0.7, long: 1.1, hero: 1.6, epic: 2.4 };
  const stagger = { chars: 0.028, words: 0.07, lines: 0.14, items: 0.09 };
  const cap = (n, each, max = 0.6) => Math.min(each, max / Math.max(1, n - 1));
  const count = (t) => (t && t.length !== undefined ? t.length : 1);

  // ── 3. Découpage du texte (au montage, jamais pendant le rendu) ──
  // by: 'chars' | 'words'. mask: chaque mot dans une fenêtre overflow:hidden (révélation par le bas).
  function split(el, { by = 'chars', mask = false } = {}) {
    const text = el.textContent;
    el.textContent = '';
    const out = [];
    text.split(/(\s+)/).forEach((w) => {
      if (!w) return;
      if (/^\s+$/.test(w)) { el.appendChild(document.createTextNode(' ')); return; }
      const word = document.createElement('span');
      word.className = 'st-word';
      if (mask) { const m = document.createElement('span'); m.className = 'st-mask'; m.appendChild(word); el.appendChild(m); }
      else el.appendChild(word);
      if (by === 'words') { word.textContent = w; out.push(word); }
      else for (const c of w) { const s = document.createElement('span'); s.className = 'st-char'; s.textContent = c; word.appendChild(s); out.push(s); }
    });
    return out;
  }

  // ── 4. Entrées et sorties typographiques ──
  function rise(tl, targets, at, o = {}) {
    tl.fromTo(targets, { opacity: 0, y: o.y ?? 42, rotation: o.rotate ?? 0, filter: `blur(${o.blur ?? 10}px)` },
      { opacity: 1, y: 0, rotation: 0, filter: 'blur(0px)', duration: o.duration ?? dur.long, ease: o.ease ?? ease.silk,
        stagger: { each: cap(count(targets), o.stagger ?? stagger.chars, o.max ?? 0.6), from: o.from ?? 'start' } }, at);
  }
  function maskUp(tl, targets, at, o = {}) {
    // .st-mask a 0,14 em de marge en haut et 0,2 em en bas : à 118 % le haut des lettres dépassait encore de 2 px
    tl.fromTo(targets, { yPercent: 140, rotation: o.rotate ?? 5 },
      { yPercent: 0, rotation: 0, duration: o.duration ?? dur.long, ease: o.ease ?? ease.silk, stagger: cap(count(targets), o.stagger ?? stagger.words, o.max ?? 0.6) }, at);
  }
  // Lettres qui se resserrent depuis le centre : remplace toute animation de letter-spacing.
  function converge(tl, letters, at, o = {}) {
    const c = (letters.length - 1) / 2, spread = o.spread ?? 60;
    letters.forEach((l, i) => tl.fromTo(l, { opacity: 0, x: (i - c) * spread, filter: `blur(${o.blur ?? 16}px)` },
      { opacity: 1, x: 0, filter: 'blur(0px)', duration: o.duration ?? dur.hero, ease: o.ease ?? ease.silk }, at + Math.abs(i - c) * (o.stagger ?? 0.06)));
  }
  function pop(tl, targets, at, o = {}) {
    const s = spring({ response: o.response ?? 0.45, damping: o.damping ?? 0.8 });
    tl.fromTo(targets, { opacity: 0, scale: o.from ?? 0.6, y: o.y ?? 0 },
      { opacity: 1, scale: 1, y: 0, duration: s.duration, ease: s.ease, stagger: cap(count(targets), o.stagger ?? stagger.items, o.max ?? 0.5) }, at);
  }
  function leave(tl, targets, at, o = {}) {
    tl.fromTo(targets, { filter: 'blur(0px)' }, { opacity: 0, y: o.y ?? -30, filter: `blur(${o.blur ?? 8}px)`, duration: o.duration ?? dur.short,
      ease: o.ease ?? ease.exit, stagger: cap(count(targets), o.stagger ?? 0.02, 0.25), immediateRender: false }, at);
  }

  // ── 5. Vie continue : rien ne s'arrête tout à fait. Écrit les propriétés CSS individuelles
  // translate / rotate / scale, qui se composent avec le transform de GSAP sans le toucher. ──
  function life(tl, els, start, end, o = {}) {
    els = Array.from(els.length !== undefined ? els : [els]);
    const r = rng(o.seed ?? 3), P = els.map(() => ({ a: r() * 6.28, b: r() * 6.28, c: r() * 6.28, f: 0.8 + r() * 0.4 }));
    const A = { x: o.x ?? 3, y: o.y ?? 6, r: o.rotate ?? 0.35, s: o.scale ?? 0.006 }, per = o.period ?? 5, fadeIn = o.fadeIn ?? 0.8;
    const apply = (t) => els.forEach((el, i) => {
      const p = P[i], w = ((2 * Math.PI) / per) * p.f, k = ease.breath(clamp(t / fadeIn));
      el.style.translate = `${(A.x * Math.sin(w * t + p.a) * k).toFixed(2)}px ${(A.y * Math.sin(w * 0.9 * t + p.b) * k).toFixed(2)}px`;
      el.style.rotate = `${(A.r * Math.sin(w * 0.7 * t + p.c) * k).toFixed(3)}deg`;
      el.style.scale = `${(1 + A.s * Math.sin(w * 0.8 * t + p.b) * k).toFixed(4)}`;
    });
    const d = end - start, px = { t: 0 };
    tl.fromTo(px, { t: 0 }, { t: d, duration: d, ease: 'none', onUpdate: () => apply(px.t) }, start);
    apply(0);
  }

  // ── 6. Caméra 2.5D : une caméra virtuelle pilote des calques à différentes profondeurs (parallaxe),
  // avec mise au point (profondeur de champ) et micro-dérive « à l'épaule ». Les calques ne portent
  // que la caméra : le contenu animé vit À L'INTÉRIEUR des calques. ──
  // layers : [{ el, depth, blur }]  (0.3 = fond lointain, 1 = sujet, 1.6+ = premier plan ; blur:false = jamais flouté, ex. le texte)
  // keys   : [{ t, x, y, s, rx, ry, rz, f, ease }] en secondes de la timeline. f = profondeur nette.
  function camera(tl, layers, o) {
    const props = ['x', 'y', 's', 'rx', 'ry', 'rz', 'f'], K = [];
    o.keys.forEach((k, i) => {
      const prev = K[i - 1] || { x: 0, y: 0, s: 1, rx: 0, ry: 0, rz: 0, f: 1 }, c = { t: k.t, ease: k.ease || ease.glide };
      props.forEach((q) => { c[q] = k[q] ?? prev[q]; });
      K.push(c);
    });
    const D = Object.assign({ x: 5, y: 4, r: 0.12, period: 9 }, o.drift || {}), dof = o.dof;
    const state = (t) => {
      let i = 0;
      while (i < K.length - 1 && t >= K[i + 1].t) i++;
      const a = K[i], b = K[Math.min(i + 1, K.length - 1)], span = b.t - a.t, p = span > 0 ? b.ease(clamp((t - a.t) / span)) : 1, c = {};
      props.forEach((q) => { c[q] = lerp(a[q], b[q], p); });
      const w = (2 * Math.PI) / D.period;
      c.x += D.x * Math.sin(w * t); c.y += D.y * Math.sin(w * 0.77 * t + 1.3); c.rz += D.r * Math.sin(w * 0.6 * t + 0.4);
      return c;
    };
    const apply = (t) => {
      const c = state(t);
      layers.forEach(({ el, depth = 1, blur = true }) => {
        el.style.transform = `translate3d(${(c.x * depth).toFixed(2)}px, ${(c.y * depth).toFixed(2)}px, 0) rotateX(${(c.rx * depth).toFixed(3)}deg) rotateY(${(c.ry * depth).toFixed(3)}deg) rotate(${c.rz.toFixed(3)}deg) scale(${(1 + (c.s - 1) * depth).toFixed(4)})`;
        if (dof && blur) { const b = Math.min(dof.max ?? 14, Math.abs(depth - c.f) * (dof.k ?? 10)); el.style.filter = b > 0.05 ? `blur(${b.toFixed(2)}px)` : 'none'; }
      });
    };
    const s0 = o.start ?? 0, d = (o.end ?? K[K.length - 1].t) - s0, px = { t: s0 };
    tl.fromTo(px, { t: s0 }, { t: s0 + d, duration: d, ease: 'none', onUpdate: () => apply(px.t) }, s0);
    apply(s0);
  }

  // ── 7. Finitions ──
  // Grain de film : tuiles de bruit pré-calculées, choisies par numéro d'image (déterministe).
  function grain(canvas, o = {}) {
    const ctx = canvas.getContext('2d'), W = canvas.width, H = canvas.height, N = o.tiles ?? 6, S = o.size ?? 256, fps = o.fps ?? 25, r = rng(o.seed ?? 9);
    const tiles = [];
    for (let k = 0; k < N; k++) {
      const c = document.createElement('canvas'); c.width = c.height = S;
      const g = c.getContext('2d'), img = g.createImageData(S, S);
      for (let i = 0; i < S * S; i++) { const v = 128 + (r() + r() + r() - 1.5) * 110 * (o.contrast ?? 1); img.data[i * 4] = img.data[i * 4 + 1] = img.data[i * 4 + 2] = v; img.data[i * 4 + 3] = 255; }
      g.putImageData(img, 0, 0); tiles.push(ctx.createPattern(c, 'repeat'));
    }
    const offs = []; for (let k = 0; k < 64; k++) offs.push([Math.floor(r() * S), Math.floor(r() * S)]);
    return (t) => {
      const f = Math.floor(t * fps + 1e-6), [ox, oy] = offs[f % 64];
      ctx.save(); ctx.clearRect(0, 0, W, H); ctx.translate(-ox, -oy); ctx.fillStyle = tiles[f % N]; ctx.fillRect(ox, oy, W, H); ctx.restore();
    };
  }
  // Pilote unique pour les rendus canvas (grain, particules…) sur toute la durée.
  function drive(tl, start, end, renders) {
    const px = { t: start }, all = () => renders.forEach((f) => f(px.t));
    tl.fromTo(px, { t: start }, { t: end, duration: end - start, ease: 'none', onUpdate: all }, start);
    all();
  }
  // Reflet de lumière qui traverse une surface (.st-sheen dans un parent .st-sheen-host).
  function sweep(tl, sheen, at, o = {}) {
    tl.fromTo(sheen, { xPercent: -160, opacity: 0 }, { xPercent: 220, opacity: 1, duration: o.duration ?? 1.4, ease: o.ease ?? ease.glide }, at);
  }

  // ── 8. Transitions : jamais de coupe sèche hors d'un temps fort. ──
  function iris(tl, el, at, o = {}) {
    const x = o.x ?? '50%', y = o.y ?? '50%';
    tl.fromTo(el, { clipPath: `circle(0% at ${x} ${y})` }, { clipPath: `circle(${o.r ?? 120}% at ${x} ${y})`, duration: o.duration ?? dur.hero, ease: o.ease ?? ease.glide }, at);
  }
  function wipe(tl, el, at, o = {}) {
    const from = { left: 'inset(0% 100% 0% 0%)', right: 'inset(0% 0% 0% 100%)', up: 'inset(100% 0% 0% 0%)', down: 'inset(0% 0% 100% 0%)' }[o.dir ?? 'left'];
    tl.fromTo(el, { clipPath: from }, { clipPath: 'inset(0% 0% 0% 0%)', duration: o.duration ?? dur.long, ease: o.ease ?? ease.glide }, at);
  }
  // Traversée : la scène sortante fonce vers la caméra et se dissout, l'entrante arrive de derrière.
  function pushThrough(tl, outEl, inEl, at, o = {}) {
    const d = o.duration ?? 0.8;
    tl.fromTo(outEl, { scale: 1, opacity: 1, filter: 'blur(0px)' }, { scale: o.outScale ?? 1.4, opacity: 0, filter: 'blur(16px)', duration: d, ease: ease.accel, immediateRender: false }, at);
    tl.fromTo(inEl, { scale: o.inScale ?? 0.84, opacity: 0, filter: 'blur(16px)' }, { scale: 1, opacity: 1, filter: 'blur(0px)', duration: d * 1.4, ease: ease.silk }, at + d * 0.4);
  }

  window.STUDIO = { ease, bezier, spring, dur, stagger, cap, rng, split, rise, maskUp, converge, pop, leave, life, camera, grain, drive, sweep, iris, wipe, pushThrough };
})();
