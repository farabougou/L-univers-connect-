# GimSo « Chez Madame » — pub mode Bogolan, 32 s, vertical 1080×1920, 25 i/s. Vidéos réelles du TikTok @gims_soumaila.
# Footage lives in index.html (root tracks); scenes are sub-compositions layered above (transparent) or opaque cards.
import os, json
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, TOTAL = 1080, 1920, 32
WINE, DEEP, GOLD, PINK, CREAM, INK = '#6E0F14', '#3A070B', '#E3B34C', '#F08BC4', '#FBEFE3', '#1A0406'

# (id, src, start, duration, media-start, style) — root video clips
CLIPS = [('h1', 'cape-gros', 0.0, 0.9, 0.3, ''), ('h2', 'blanc-gros', 0.9, 0.9, 0.4, ''), ('h3', 'noir-gros', 1.8, 0.9, 0.6, ''), ('h4', 'capuche-gros', 2.7, 1.1, 1.0, ''),
         ('l1', 'cape-capuche', 7.0, 3.1, 0.0, ''), ('l2', 'poncho-blanc', 10.0, 3.1, 0.0, ''), ('l3', 'poncho-noir', 13.0, 3.1, 0.0, ''), ('l4', 'gilet-franges', 16.0, 3.1, 0.0, ''),
         ('ac', 'casquettes', 19.0, 4.0, 0.0, 'left:180px; top:420px; width:720px; height:1280px; border-radius:28px;'),
         ('pr', 'capuche-gros', 23.0, 3.2, 0.0, '')]
# (id, start, duration, opaque, below_video)
SC = [('01-accroche', 0, 3.8, False), ('02-marque', 3.6, 3.6, True), ('03-looks', 7.0, 12.1, False), ('04-acc-bg', 19.0, 4.0, True),
      ('05-acc', 19.0, 4.1, False), ('06-preuve', 23.0, 3.3, False), ('07-contact', 25.9, 6.1, True)]
BELOW = {'04-acc-bg'}  # rendered under the footage

FONTS = '''
    @font-face { font-family: "Cinzel"; font-weight: 600; src: url("assets/fonts/cinzel-600.woff2") format("woff2"); }
    @font-face { font-family: "Playfair Display"; font-weight: 600; src: url("assets/fonts/playfair-display-latin-600-normal.woff2") format("woff2"); }
    @font-face { font-family: "Playfair Display"; font-weight: 700; src: url("assets/fonts/playfair-display-latin-700-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 500; src: url("assets/fonts/montserrat-latin-500-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 600; src: url("assets/fonts/montserrat-latin-600-normal.woff2") format("woff2"); }
    @font-face { font-family: "Great Vibes"; font-weight: 400; src: url("assets/fonts/greatvibes-400.woff2") format("woff2"); }
'''
CSS = f'''
    .X-a {{ position: absolute; }}
    .X-c {{ left: 0; right: 0; text-align: center; }}
    .X-wine {{ position: absolute; inset: 0; background: radial-gradient(85% 60% at 50% 45%, #8C1A21 0%, {WINE} 45%, {DEEP} 100%); }}
    .X-kick {{ font-family: "Montserrat"; font-weight: 600; font-size: 26px; letter-spacing: 0.32em; color: {GOLD}; white-space: nowrap; }}
    .X-t1 {{ font-family: "Playfair Display"; font-weight: 700; font-size: 96px; line-height: 1.05; color: {CREAM}; white-space: nowrap; }}
    .X-t2 {{ font-family: "Playfair Display"; font-weight: 600; font-size: 64px; line-height: 1.1; color: {GOLD}; white-space: nowrap; }}
    .X-sc {{ font-family: "Great Vibes"; color: {PINK}; white-space: nowrap; line-height: 1; }}
    .X-logo {{ font-family: "Cinzel"; font-weight: 600; color: {GOLD}; letter-spacing: 0.06em; white-space: nowrap; line-height: 1; }}
    .X-cm {{ font-family: "Montserrat"; font-weight: 500; color: {PINK}; letter-spacing: 0.42em; white-space: nowrap; }}
    .X-mk {{ position: absolute; overflow: hidden; }}
    .X-mk > span {{ display: inline-block; }}
    .X-band {{ position: absolute; left: 0; width: 1080px; }}
    .X-band svg {{ display: block; }}
'''

def tile(pid, ink, bg):
    """200×200 Bogolan tile: dot grid, bars, cross, zigzag, thick hand-drawn rules."""
    s = f'<pattern id="{pid}" width="200" height="200" patternUnits="userSpaceOnUse"><rect width="200" height="200" fill="{bg}"/>'
    s += f'<g fill="{ink}">' + ''.join(f'<circle cx="{22 + i * 28}" cy="{22 + j * 28}" r="6"/>' for i in range(3) for j in range(3))
    s += ''.join(f'<rect x="{116 + i * 20}" y="12" width="8" height="76" rx="4"/>' for i in range(4))
    s += '<rect x="0" y="94" width="200" height="10" rx="4"/><rect x="94" y="0" width="10" height="200" rx="4"/>'
    s += ''.join(f'<circle cx="{x}" cy="{y}" r="5"/>' for x, y in [(116, 116), (180, 116), (116, 180), (180, 180)])
    s += f'</g><g stroke="{ink}" stroke-width="9" stroke-linecap="round" fill="none"><path d="M 14 130 L 80 190 M 80 130 L 14 190"/>'
    s += '<path d="M 112 140 L 128 124 L 144 140 L 160 124 L 176 140 L 192 124 M 112 168 L 128 152 L 144 168 L 160 152 L 176 168 L 192 152"/></g></pattern>'
    return s

def band(bid, y, h=80, ink=GOLD, bg=DEEP):
    return f'    <div class="X-band" id="{bid}" style="top:{y}px; height:{h}px"><svg width="1280" height="{h}"><defs>{tile(bid + "p", ink, bg)}</defs><rect width="1280" height="{h}" fill="url(#{bid}p)"/></svg></div>\n'

def logo(y, size=170, tag=True):
    t = f'    <div class="X-a X-c X-cm" id="X-cm" style="top:{y + int(size * 1.08)}px; font-size:{int(size * 0.2)}px">CHEZ MADAME</div>\n' if tag else ''
    return f'    <div class="X-a X-c X-logo" id="X-lg" style="top:{y}px; font-size:{size}px">GIMSO</div>\n' + t

def mask(sel, at, d=0.6, frm=110):
    return f'      tl.fromTo(R("{sel}"), {{ yPercent: {frm} }}, {{ yPercent: 0, duration: {d}, ease: "power3.out" }}, {at});\n'

def fade_up(sel, at, d=0.6, y=24):
    return f'      tl.fromTo(R("{sel}"), {{ opacity: 0, y: {y} }}, {{ opacity: 1, y: 0, duration: {d}, ease: "power3.out" }}, {at});\n'

F = {}
# ── 01 · 0–3.6 s · hook over fast close-up cuts ─────────────────────────────
F['01-accroche'] = (f'''
    #X-grad {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(26,4,6,0.55) 0%, rgba(26,4,6,0) 28%, rgba(26,4,6,0) 52%, rgba(26,4,6,0.85) 78%, rgba(26,4,6,0.95) 100%); }}
    #X-flash {{ position: absolute; inset: 0; background: {CREAM}; opacity: 0; }}
''', '''    <div id="X-grad"></div>
    <div id="X-flash"></div>
    <div class="X-a X-kick X-c" id="X-k" style="top:1330px">NOUVELLE TENDANCE</div>
    <div class="X-a X-c X-mk" style="top:1380px; height:120px"><span class="X-t1" id="X-s1">Le Bogolan</span></div>
    <div class="X-a X-c X-mk" style="top:1505px; height:90px"><span class="X-t2" id="X-s2" style="font-size:54px">comme vous ne l'avez</span></div>
    <div class="X-a X-c X-mk" style="top:1580px; height:90px"><span class="X-t2" id="X-s3" style="font-size:54px">jamais porté.</span></div>
''', '''      [0.9, 1.8, 2.7].forEach((t) => tl.fromTo(R("#X-flash"), { opacity: 0.55 }, { opacity: 0, duration: 0.22, ease: "power2.out", immediateRender: false }, t));
      tl.fromTo(R("#X-k"), { opacity: 0 }, { opacity: 1, duration: 0.4 }, 0.15);
''' + mask('#X-s1', 0.2, 0.55) + mask('#X-s2', 0.75, 0.5) + mask('#X-s3', 1.0, 0.5) + '''      tl.to([R("#X-k"), R("#X-s1"), R("#X-s2"), R("#X-s3")], { opacity: 0, y: -20, duration: 0.3, ease: "power2.in" }, 3.4);
''', 'transparent')

# ── 02 · 3.6–7 s · brand card ───────────────────────────────────────────────
STROKES = ['M -20 420 L 100 340 L 220 420 L 340 340 L 460 420 L 580 340 L 700 420 L 820 340 L 940 420 L 1100 320',
           'M -20 1500 L 100 1580 L 220 1500 L 340 1580 L 460 1500 L 580 1580 L 700 1500 L 820 1580 L 940 1500 L 1100 1600']
F['02-marque'] = (f'''
    #X-svg {{ position: absolute; left: 0; top: 0; }}
    #X-rule {{ position: absolute; left: 340px; top: 1112px; width: 400px; height: 3px; background: {GOLD}; transform-origin: 50% 50%; }}
''', f'''    <div class="X-wine"></div>
    <svg id="X-svg" width="1080" height="1920"><g stroke="{GOLD}" stroke-opacity="0.45" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" fill="none">''' +
 ''.join(f'<path class="X-ln" d="{d}"/>' for d in STROKES) + f'''</g><g fill="{GOLD}" fill-opacity="0.45">''' +
 ''.join(f'<circle class="X-dt" cx="{x}" cy="{y}" r="8"/>' for y in (500, 1420) for x in range(70, 1081, 94)) + '''</g></svg>
''' + logo(790, 190) + '''    <div id="X-rule"></div>
    <div class="X-a X-kick X-c" id="X-k" style="top:1150px">MODE BOGOLAN · BAMAKO</div>
''', '''      RA(".X-ln").forEach((p, i) => { const L = p.getTotalLength(); tl.fromTo(p, { attr: { "stroke-dasharray": L + " " + L, "stroke-dashoffset": L } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.2, ease: "power2.inOut" }, 0.1 + i * 0.15); });
      RA(".X-dt").forEach((d, i) => tl.fromTo(d, { attr: { r: 0 } }, { attr: { r: 8 }, duration: 0.25, ease: "back.out(3)" }, 0.4 + (i % 12) * 0.04));
      tl.fromTo(R("#X-lg"), { opacity: 0, scale: 1.25, filter: "blur(12px)" }, { opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.9, ease: "power3.out" }, 0.25);
      tl.fromTo(R("#X-cm"), { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, 0.85);
      tl.fromTo(R("#X-rule"), { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: "power2.inOut" }, 1.1);
      tl.fromTo(R("#X-k"), { opacity: 0 }, { opacity: 1, duration: 0.6 }, 1.35);
      tl.to(R("#X-lg"), { scale: 1.04, duration: 2.0, ease: "none" }, 1.2);
''', 'opaque')

# ── 03 · 7–19 s · four looks, labelled, wine wipes on every cut ─────────────
LOOKS = [('Cape à capuche', 'Bogolan · motif Afrique'), ('Poncho ample', 'Bogolan blanc'), ('Poncho noir', 'Bogolan · motifs blancs'), ('Gilet à franges', 'Bogolan ocre')]
lab = ''.join(f'''    <div class="X-lab" id="X-lb{i}"><b>0{i + 1}</b><div class="X-mk" style="position:relative; height:92px"><span class="X-nm" id="X-nm{i}">{n}</span></div><div class="X-sub" id="X-sb{i}">{s}</div></div>\n''' for i, (n, s) in enumerate(LOOKS))
F['03-looks'] = (f'''
    #X-grad {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(26,4,6,0.5) 0%, rgba(26,4,6,0) 16%, rgba(26,4,6,0) 62%, rgba(26,4,6,0.88) 86%); }}
    .X-lab {{ position: absolute; left: 80px; top: 1500px; width: 920px; opacity: 0; }}
    .X-lab b {{ display: block; font-family: "Montserrat"; font-weight: 600; font-size: 30px; letter-spacing: 0.2em; color: {GOLD}; border-left: 4px solid {GOLD}; padding-left: 16px; margin-bottom: 10px; }}
    .X-nm {{ font-family: "Playfair Display"; font-weight: 700; font-size: 82px; line-height: 92px; color: {CREAM}; white-space: nowrap; }}
    .X-sub {{ margin-top: 6px; font-family: "Montserrat"; font-weight: 500; font-size: 30px; letter-spacing: 0.08em; color: {PINK}; }}
    #X-wmb {{ position: absolute; left: 340px; top: 92px; width: 400px; height: 120px; border-radius: 22px; background: rgba(26,4,6,0.72); }}
    #X-wm {{ top: 110px; font-size: 54px; }}
    #X-wmc {{ top: 172px; font-size: 18px; color: #FFE6F3; }}
    #X-wipe {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; background: {WINE}; }}
    #X-wipe i {{ position: absolute; left: -60px; top: 0; width: 60px; height: 100%; background: {GOLD}; }}
''', '''    <div id="X-grad"></div>
    <div id="X-wmb"></div>
    <div class="X-a X-c X-logo" id="X-wm" data-layout-allow-overlap>GIMSO</div>
    <div class="X-a X-c X-cm" id="X-wmc" data-layout-allow-overlap>CHEZ MADAME</div>
''' + lab + '''    <div id="X-wipe" data-layout-allow-overflow><i></i></div>
''', '''      tl.fromTo([R("#X-wmb"), R("#X-wm"), R("#X-wmc")], { opacity: 0 }, { opacity: 1, duration: 0.6 }, 0.2);
      tl.set(R("#X-wipe"), { xPercent: 110 }, 0);
      [0, 1, 2, 3].forEach((i) => {
        const t0 = i * 3;
        tl.fromTo(R("#X-lb" + i), { opacity: 0 }, { opacity: 1, duration: 0.01 }, t0 + 0.35);
        tl.fromTo(R("#X-lb" + i + " b"), { opacity: 0, x: -30 }, { opacity: 1, x: 0, duration: 0.45, ease: "power3.out" }, t0 + 0.35);
        tl.fromTo(R("#X-nm" + i), { yPercent: 110 }, { yPercent: 0, duration: 0.55, ease: "power3.out" }, t0 + 0.45);
        tl.fromTo(R("#X-sb" + i), { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" }, t0 + 0.7);
        tl.to(R("#X-lb" + i), { opacity: 0, duration: 0.2 }, t0 + 2.75);
        if (i < 3) {  // wipe hides the cut at t0 + 3
          tl.fromTo(R("#X-wipe"), { xPercent: 110 }, { xPercent: 0, duration: 0.28, ease: "power3.in", immediateRender: false }, t0 + 2.72);
          tl.to(R("#X-wipe"), { xPercent: -115, duration: 0.32, ease: "power3.out" }, t0 + 3.0);
        }
      });
''', 'transparent')

# ── 04/05 · 19–23 s · accessories: framed clip on wine ─────────────────────
F['04-acc-bg'] = ('', '    <div class="X-wine"></div>\n' + band('X-b1', 0, 70) + band('X-b2', 1850, 70), '''      tl.fromTo(R("#X-b1 svg"), { x: 0 }, { x: -200, duration: 4.0, ease: "none" }, 0);
      tl.fromTo(R("#X-b2 svg"), { x: -200 }, { x: 0, duration: 4.0, ease: "none" }, 0);
''', 'opaque')
F['05-acc'] = (f'''
    #X-frame {{ position: absolute; left: 160px; top: 400px; width: 760px; height: 1320px; border: 3px solid {GOLD}; border-radius: 40px; }}
''', '''    <div id="X-frame"></div>
    <div class="X-a X-kick X-c" id="X-k" style="top:140px">POUR COMPLÉTER LE LOOK</div>
    <div class="X-a X-c X-mk" style="top:190px; height:110px"><span class="X-t1" id="X-s1" style="font-size:84px">Casquettes</span></div>
    <div class="X-a X-c X-mk" style="top:290px; height:90px"><span class="X-t2" id="X-s2">&amp; sacs en Bogolan</span></div>
    <div class="X-a X-c X-sc" id="X-s3" style="top:1745px; font-size:76px">assortis à vos tenues</div>
''', fade_up('#X-k', 0.2, 0.5, 12) + mask('#X-s1', 0.3) + mask('#X-s2', 0.55) + '''      tl.fromTo(R("#X-frame"), { opacity: 0, scale: 1.06 }, { opacity: 1, scale: 1, duration: 0.7, ease: "power3.out" }, 0.35);
      tl.fromTo(R("#X-s3"), { opacity: 0, clipPath: "inset(0% 100% 0% 0%)" }, { opacity: 1, clipPath: "inset(0% 0% 0% 0%)", duration: 0.9, ease: "power2.inOut" }, 1.2);
''', 'transparent')

# ── 06 · 23–26.2 s · social proof over close-up ────────────────────────────
F['06-preuve'] = (f'''
    #X-dim {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(26,4,6,0.2) 0%, rgba(26,4,6,0.78) 45%, rgba(26,4,6,0.9) 100%); }}
    #X-num {{ top: 1040px; font-family: "Cinzel"; font-weight: 600; font-size: 200px; line-height: 1; color: {GOLD}; }}
    #X-lbl {{ top: 1260px; font-family: "Playfair Display"; font-weight: 600; font-size: 60px; color: {CREAM}; }}
    #X-likes {{ top: 1360px; font-family: "Montserrat"; font-weight: 600; font-size: 36px; letter-spacing: 0.06em; color: {PINK}; }}
''', '''    <div id="X-dim"></div>
    <div class="X-a X-kick X-c" id="X-k" style="top:980px">ILS NOUS SUIVENT DÉJÀ</div>
    <div class="X-a X-c" id="X-num"><span id="X-n">0</span> K</div>
    <div class="X-a X-c" id="X-lbl">abonnés sur TikTok</div>
    <div class="X-a X-c" id="X-likes">+ 7,5 millions de j'aime</div>
''', '''      tl.fromTo(R("#X-dim"), { opacity: 0 }, { opacity: 1, duration: 0.5 }, 0.0);
      tl.fromTo(R("#X-k"), { opacity: 0 }, { opacity: 1, duration: 0.4 }, 0.3);
      tl.fromTo(R("#X-num"), { opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: 0.5, ease: "back.out(1.8)" }, 0.35);
      const cnt = { v: 0 }, el = R("#X-n");
      tl.fromTo(cnt, { v: 0 }, { v: 322, duration: 1.3, ease: "power2.out", onUpdate: () => { el.textContent = Math.round(cnt.v); } }, 0.4);
''' + fade_up('#X-lbl', 0.9) + fade_up('#X-likes', 1.4, 0.5, 16), 'transparent')

# ── 07 · 26.2–32 s · contact ───────────────────────────────────────────────
PH = f'<svg width="50" height="50" viewBox="0 0 24 24"><path fill="{GOLD}" d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.2.2 2.4.6 3.6.1.3 0 .7-.2 1z"/></svg>'
TT = f'<svg width="34" height="34" viewBox="0 0 24 24"><path fill="{CREAM}" d="M16.5 3c.4 2.2 1.8 3.6 4 3.8v3.1a7.4 7.4 0 0 1-4-1.2v6.2A6 6 0 1 1 10.4 9v3.2a2.9 2.9 0 1 0 2.1 2.8V3z"/></svg>'
F['07-contact'] = (f'''
    #X-cta {{ top: 900px; font-family: "Playfair Display"; font-weight: 700; font-size: 80px; color: {CREAM}; }}
    #X-pill {{ position: absolute; left: 140px; top: 1050px; width: 800px; height: 130px; border-radius: 65px; border: 3px solid {GOLD}; background: rgba(227,179,76,0.12); }}
    #X-tel {{ top: 1050px; height: 130px; display: flex; justify-content: center; align-items: center; gap: 24px; }}
    #X-tel b {{ font-family: "Montserrat"; font-weight: 600; font-size: 72px; color: #FFFFFF; letter-spacing: 0.04em; }}
    #X-soc {{ top: 1240px; display: flex; justify-content: center; align-items: center; gap: 14px; font-family: "Montserrat"; font-weight: 500; font-size: 36px; color: {CREAM}; }}
    #X-fb {{ top: 1305px; font-family: "Montserrat"; font-weight: 500; font-size: 30px; color: {CREAM}; opacity: 0.8; }}
''', '    <div class="X-wine"></div>\n' + band('X-b1', 120, 80) + band('X-b2', 1700, 80) + logo(470, 190) + f'''    <div class="X-a X-c" id="X-cta">Commandez maintenant</div>
    <div id="X-pill"></div>
    <div class="X-a X-c" id="X-tel">{PH}<b>76 67 03 42</b></div>
    <div class="X-a X-c" id="X-soc">{TT}<span>@gims_soumaila</span></div>
    <div class="X-a X-c" id="X-fb">Facebook : GimSo · Bamako</div>
''', '''      tl.fromTo([R("#X-b1"), R("#X-b2")], { clipPath: "inset(0% 50% 0% 50%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.8, ease: "power2.inOut" }, 0);
      tl.fromTo(R("#X-b1 svg"), { x: 0 }, { x: -200, duration: 5.8, ease: "none" }, 0);
      tl.fromTo(R("#X-b2 svg"), { x: -200 }, { x: 0, duration: 5.8, ease: "none" }, 0);
      tl.fromTo(R("#X-lg"), { opacity: 0, scale: 1.2, filter: "blur(10px)" }, { opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.8, ease: "power3.out" }, 0.15);
      tl.fromTo(R("#X-cm"), { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.5 }, 0.6);
''' + fade_up('#X-cta', 0.9) + '''      tl.fromTo(R("#X-pill"), { opacity: 0, scaleX: 0.6 }, { opacity: 1, scaleX: 1, duration: 0.6, ease: "power3.out" }, 1.4);
''' + fade_up('#X-tel', 1.55, 0.6, 18) + fade_up('#X-soc', 2.1, 0.5, 14) + fade_up('#X-fb', 2.35, 0.5, 14) + '''      tl.to(R("#X-pill"), { boxShadow: "0 0 50px rgba(227,179,76,0.6)", duration: 0.6, ease: "sine.inOut", yoyo: true, repeat: 3 }, 2.8);
''', 'opaque')

def frame(fid, dur, css, html, js, bg):
    pre = 'g' + fid[:2]
    sub = lambda s: s.replace('X-', pre + '-')
    back = INK if bg == 'opaque' else 'transparent'
    return f'''<template>
  <style>
{FONTS}
    #root {{ position: absolute; inset: 0; width: 100%; height: 100%; overflow: hidden; font-family: "Montserrat", sans-serif; color: {CREAM}; background: {back}; }}
{sub(CSS)}
{sub(css)}
  </style>
  <div id="root" data-composition-id="{fid}" data-start="0" data-duration="{dur}" data-width="{W}" data-height="{H}">
    <div id="{pre}-clip" class="clip" data-start="0" data-duration="{dur}" data-track-index="0" style="position:absolute; inset:0"></div>
{sub(html)}
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
      const R = (s) => document.querySelector('[data-composition-id="{fid}"] ' + s);
      const RA = (s) => document.querySelectorAll('[data-composition-id="{fid}"] ' + s);
{sub(js)}
      tl.to({{}}, {{ duration: {dur} }}, 0);
      window.__timelines["{fid}"] = tl;
    }})();
  </script>
</template>
'''

os.makedirs(f'{P}/compositions/frames', exist_ok=True)
below, above, trans = '', '', ''
for i, (fid, st, dur, opaque) in enumerate(SC):
    css, html, js, bg = F[fid]
    open(f'{P}/compositions/frames/{fid}.html', 'w').write(frame(fid, dur, css, html, js, bg))
    el = f'      <div id="el-{fid}" class="scene" data-composition-id="{fid}" data-composition-src="compositions/frames/{fid}.html" data-start="{st}" data-duration="{dur}" data-track-index="{2 + i}"></div>\n'
    if fid in BELOW: below += el
    else: above += el
vids, vjs = '', ''
for i, (vid, src, st, dur, ms, style) in enumerate(CLIPS):
    full = style == ''
    css = 'left:0; top:0; width:1080px; height:1920px;' if full else style
    vids += f'      <video id="v-{vid}" class="clip vid" src="assets/clips/{src}.mp4" data-start="{st}" data-duration="{dur}" data-media-start="{ms}" data-track-index="{i % 2}" muted playsinline style="{css}"></video>\n'
    # slow push-in on every shot keeps the footage alive
    vjs += f'        tl.fromTo("#v-{vid}", {{ scale: {1.0 if full else 0.96} }}, {{ scale: {1.08 if full else 1.0}, duration: {dur}, ease: "none" }}, {st});\n'
# scene cross-fades
vjs += '        tl.fromTo("#el-02-marque", { opacity: 0 }, { opacity: 1, duration: 0.2, ease: "power2.out" }, 3.6);\n'
vjs += '        tl.to("#el-02-marque", { clipPath: "inset(0% 0% 100% 0%)", duration: 0.35, ease: "power3.inOut" }, 6.85);\n'
vjs += '        tl.fromTo("#el-04-acc-bg", { clipPath: "inset(100% 0% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.4, ease: "power3.inOut" }, 19.0);\n'
vjs += '        tl.fromTo("#v-ac", { opacity: 0 }, { opacity: 1, duration: 0.4 }, 19.2);\n'
vjs += '        tl.fromTo("#el-07-contact", { clipPath: "circle(0% at 50% 50%)" }, { clipPath: "circle(75% at 50% 50%)", duration: 0.6, ease: "power3.inOut" }, 25.9);\n'
VO = f'{P}/assets/voice/voice.json'
voice = os.path.exists(VO)
vo = ''.join(f'      <audio id="el-vo{i + 1}" src="{src}" data-start="{at}" data-duration="{d}" data-track-index="{20 + i}" data-volume="1"></audio>\n' for i, (src, at, d) in enumerate(json.load(open(VO)))) if voice else ''
idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {INK}; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {INK}; }}
      .scene {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
      .vid {{ position: absolute; object-fit: cover; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
{below}{vids}{above}
      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="15" data-volume="{0.22 if voice else 0.75}"></audio>
{vo}    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
      (function () {{ var tl = window.__timelines["main"];
{vjs}        tl.to({{}}, {{ duration: {TOTAL} }}, 0);
      }})();
    </script>
  </body>
</html>
'''
open(f'{P}/index.html', 'w').write(idx)
print('ok')
