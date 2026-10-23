/* SensExpress — « Aura » : seek-safe atmosphere for the diffuser film.
   Every builder returns render(t, k): a pure function of local time (no state carried between frames). */
(function () {
  function rng(s) { return () => { s |= 0; s = (s + 0x6d2b79f5) | 0; let r = Math.imul(s ^ (s >>> 15), 1 | s); r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r; return ((r ^ (r >>> 14)) >>> 0) / 4294967296; }; }
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const smooth = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };

  // pre-rendered soft sprite (radial falloff) tinted per use
  function sprite(rgb, size = 128, core = 0.0) {
    const c = document.createElement("canvas"); c.width = c.height = size; const g = c.getContext("2d");
    const gr = g.createRadialGradient(size / 2, size / 2, size * core * 0.5, size / 2, size / 2, size / 2);
    gr.addColorStop(0, `rgba(${rgb},1)`); gr.addColorStop(0.35, `rgba(${rgb},0.55)`); gr.addColorStop(0.7, `rgba(${rgb},0.16)`); gr.addColorStop(1, `rgba(${rgb},0)`);
    g.fillStyle = gr; g.fillRect(0, 0, size, size); return c;
  }

  // ── living background: drifting golden halos, light dust, a slow light sweep ──
  function backdrop(canvas, o = {}) {
    const ctx = canvas.getContext("2d"), W = canvas.width, H = canvas.height, r = rng(o.seed || 5);
    const gold = sprite("212,175,55", 256), champ = sprite("245,230,211", 64);
    const halos = []; for (let i = 0; i < 7; i++) halos.push({ x: r(), y: r(), s: 0.45 + r() * 0.7, sp: 0.02 + r() * 0.035, ph: r() * 6.28, a: 0.10 + r() * 0.12 });
    const dust = []; for (let i = 0; i < (o.dust || 140); i++) dust.push({ x: r(), y: r(), z: 0.3 + r() * 0.7, sp: 0.006 + r() * 0.02, ph: r() * 6.28, f: r() * 20 });
    return function (t, k = 1) {
      ctx.globalCompositeOperation = "source-over"; ctx.fillStyle = "#08080C"; ctx.fillRect(0, 0, W, H);
      ctx.globalCompositeOperation = "lighter";
      for (const h of halos) {
        const x = (h.x + Math.sin(t * h.sp * 6.28 + h.ph) * 0.12) * W, y = (h.y + Math.cos(t * h.sp * 5.1 + h.ph) * 0.09) * H;
        const s = h.s * W * (1 + 0.08 * Math.sin(t * 0.5 + h.ph));
        ctx.globalAlpha = h.a * k * (0.75 + 0.25 * Math.sin(t * 0.7 + h.ph)); ctx.drawImage(gold, x - s / 2, y - s / 2, s, s);
      }
      for (const d of dust) {
        const y = ((d.y - t * d.sp + 10) % 1) * H, x = (d.x + Math.sin(t * 0.3 + d.ph) * 0.01) * W, s = 3 + d.z * 7;
        ctx.globalAlpha = (0.25 + 0.5 * d.z) * (0.5 + 0.5 * Math.sin(t * 2 + d.f)) * 0.6 * k; ctx.drawImage(champ, x - s / 2, y - s / 2, s, s);
      }
      // slow diagonal sheen
      const sx = ((t * 0.045) % 1.6 - 0.3) * W;
      const g = ctx.createLinearGradient(sx - 300, 0, sx + 300, H * 0.4);
      g.addColorStop(0, "rgba(245,230,211,0)"); g.addColorStop(0.5, `rgba(245,230,211,${0.035 * k})`); g.addColorStop(1, "rgba(245,230,211,0)");
      ctx.globalAlpha = 1; ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
    };
  }

  // ── vapour: puffs leave a nozzle, rise and slow down, undulate on layered turbulence, swell and fade ──
  function vapour(canvas, o = {}) {
    const ctx = canvas.getContext("2d"), W = canvas.width, H = canvas.height, r = rng(o.seed || 11);
    const puff = sprite(o.rgb || "250,246,240", 128);
    const n = o.n || 70, P = [];
    for (let i = 0; i < n; i++) P.push({ ph: r(), sp: 0.85 + r() * 0.35, a: 0.6 + r() * 0.4, w1: r() * 6.28, w2: r() * 6.28, sz: 0.7 + r() * 0.6, lean: (r() - 0.5) * 0.6 });
    const life = o.life || 3.2, rise = o.rise || 620, size = o.size || 60, dir = o.dir || 0; // dir: radians of the jet from vertical
    return function (t, k = 1) {
      ctx.clearRect(0, 0, W, H); if (k <= 0.001) return;
      ctx.globalCompositeOperation = "screen";
      for (const p of P) {
        const age = ((t / life) * p.sp + p.ph) % 1;          // 0 → 1 over the puff's life
        const hgt = rise * (1 - Math.pow(1 - age, 1.8));    // fast exit, slows as it rises
        const turb = Math.sin(hgt * 0.012 + t * 1.3 + p.w1) * 0.6 + Math.sin(hgt * 0.027 - t * 0.9 + p.w2) * 0.4;
        const sway = turb * (8 + hgt * 0.16) + p.lean * hgt * 0.25;
        const x = o.x + Math.sin(dir) * hgt + Math.cos(dir) * sway;
        const y = o.y - Math.cos(dir) * hgt + Math.sin(dir) * sway * 0.4;
        const s = size * p.sz * (0.35 + age * 2.6);
        const a = (o.alpha || 0.22) * p.a * smooth(age / 0.08) * Math.pow(1 - age, 1.6) * k;
        ctx.globalAlpha = a; ctx.drawImage(puff, x - s / 2, y - s / 2, s, s * (1.1 + age * 0.4));
      }
      ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
    };
  }

  // ── star projection: twinkling points with soft cross glints ──
  function stars(canvas, o = {}) {
    const ctx = canvas.getContext("2d"), W = canvas.width, H = canvas.height, r = rng(o.seed || 31);
    const dot = sprite("255,244,220", 32), S = [];
    for (let i = 0; i < (o.n || 160); i++) S.push({ x: r() * W, y: r() * H * (o.band || 0.6), z: r(), ph: r() * 6.28, f: 1 + r() * 3 });
    return function (t, k = 1) {
      ctx.clearRect(0, 0, W, H); if (k <= 0.001) return;
      ctx.globalCompositeOperation = "lighter";
      for (const s of S) {
        const tw = 0.35 + 0.65 * Math.pow(0.5 + 0.5 * Math.sin(t * s.f + s.ph), 2);
        const sz = 4 + s.z * 12, a = tw * (0.35 + 0.65 * s.z) * k;
        ctx.globalAlpha = a; ctx.drawImage(dot, s.x - sz / 2, s.y - sz / 2 + Math.sin(t * 0.2 + s.ph) * 4, sz, sz);
        if (s.z > 0.85) { ctx.globalAlpha = a * 0.5; ctx.fillStyle = "rgba(255,240,210,1)"; ctx.fillRect(s.x - sz * 1.4, s.y - 0.5, sz * 2.8, 1); ctx.fillRect(s.x - 0.5, s.y - sz * 1.4, 1, sz * 2.8); }
      }
      ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
    };
  }

  window.AURA = { backdrop, vapour, stars, _: { rng, clamp, smooth } };
})();
