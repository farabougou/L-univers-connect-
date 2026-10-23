/* Founerou Grill's — seek-safe fire effects. Every builder returns render(t): a pure function of local time. */
(function () {
  function rng(s) { return () => { s |= 0; s = (s + 0x6d2b79f5) | 0; let r = Math.imul(s ^ (s >>> 15), 1 | s); r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r; return ((r ^ (r >>> 14)) >>> 0) / 4294967296; }; }
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));

  // rising embers: small hot dots that sway and flicker
  function embers(canvas, o = {}) {
    const ctx = canvas.getContext("2d"), r = rng(o.seed || 3), n = o.n || 90, W = canvas.width, H = canvas.height;
    const P = []; for (let i = 0; i < n; i++) P.push({ x: r(), ph: r(), sp: 0.10 + r() * 0.22, sz: 1.2 + r() * 3.2, sw: 0.5 + r() * 1.5, f: r() * 20, hot: r() });
    return function (t, k = 1) {
      ctx.clearRect(0, 0, W, H); if (k <= 0.001) return;
      ctx.globalCompositeOperation = "lighter";
      for (const p of P) {
        const life = (t * p.sp + p.ph) % 1;
        const x = p.x * W + Math.sin(t * p.sw + p.ph * 12) * 40 * life + (o.drift || 0) * life;
        const y = H * (o.base || 1.02) - life * H * (o.rise || 0.9);
        const fl = 0.6 + 0.4 * Math.sin(t * 13 + p.f);
        const a = Math.sin(life * Math.PI) * fl * k * (o.alpha || 0.9);
        const c = p.hot > 0.6 ? "255,214,120" : p.hot > 0.25 ? "255,150,40" : "255,90,20";
        const g = ctx.createRadialGradient(x, y, 0, x, y, p.sz * 4);
        g.addColorStop(0, `rgba(${c},${a.toFixed(3)})`); g.addColorStop(0.35, `rgba(${c},${(a * 0.45).toFixed(3)})`); g.addColorStop(1, `rgba(${c},0)`);
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, p.sz * 4, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
    };
  }

  // flame band: additive blobs born along the bottom, rising, shrinking, cooling from yellow to red
  function flames(canvas, o = {}) {
    const ctx = canvas.getContext("2d"), r = rng(o.seed || 9), n = o.n || 220, W = canvas.width, H = canvas.height;
    const P = []; for (let i = 0; i < n; i++) P.push({ x: r(), ph: r(), sp: 0.7 + r() * 0.9, sz: 0.6 + r() * 0.8, sw: r() * 6.28 });
    const y0 = o.y || H, hgt = o.height || 520;
    return function (t, k = 1) {
      ctx.clearRect(0, 0, W, H); if (k <= 0.001) return;
      ctx.globalCompositeOperation = "lighter";
      for (const p of P) {
        const life = (t * p.sp + p.ph) % 1;
        const cx = p.x * W + Math.sin(t * 3 + p.sw + life * 4) * 26 * life;
        const cy = y0 - life * hgt * (0.55 + 0.45 * Math.sin(p.x * 17 + t * 0.7) ** 2);
        const rad = (o.size || 90) * p.sz * (1 - life * 0.75);
        const a = (o.alpha || 0.16) * (1 - life) * Math.min(1, life * 8) * k;
        const col = life < 0.25 ? "255,200,90" : life < 0.55 ? "255,120,30" : "220,50,20";
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rad);
        g.addColorStop(0, `rgba(${col},${a.toFixed(3)})`); g.addColorStop(1, `rgba(${col},0)`);
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, rad, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
    };
  }

  // spark burst from a point, starting at time t0 (radial streaks with gravity)
  function sparks(canvas, o = {}) {
    const ctx = canvas.getContext("2d"), r = rng(o.seed || 21), n = o.n || 70, W = canvas.width, H = canvas.height;
    const P = []; for (let i = 0; i < n; i++) { const a = r() * Math.PI * 2; P.push({ a, v: 500 + r() * 1100, l: 0.4 + r() * 0.6, w: 1 + r() * 2.5 }); }
    return function (t) {
      ctx.clearRect(0, 0, W, H);
      const dt = t - (o.t0 || 0); if (dt < 0 || dt > 1.4) return;
      ctx.globalCompositeOperation = "lighter"; ctx.lineCap = "round";
      for (const p of P) {
        const life = dt / p.l; if (life > 1) continue;
        const x = o.x + Math.cos(p.a) * p.v * dt, y = o.y + Math.sin(p.a) * p.v * dt + 900 * dt * dt;
        const tx = x - Math.cos(p.a) * p.v * 0.035, ty = y - (Math.sin(p.a) * p.v + 1800 * dt) * 0.035;
        ctx.strokeStyle = `rgba(255,${190 - life * 100 | 0},70,${(1 - life).toFixed(3)})`; ctx.lineWidth = p.w;
        ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(x, y); ctx.stroke();
      }
      ctx.globalCompositeOperation = "source-over";
    };
  }

  window.FG = { embers, flames, sparks, _: { rng, clamp } };
})();
