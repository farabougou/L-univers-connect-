# Founerou Grill's (Ivry-sur-Seine) — pub motion design, vertical 1080×1920, 25 i/s, 36,5 s.
# Références : Pinterest A (plats détourés qui glissent sur fond uni, dérive lente) + Pinterest B (fonds pleins,
# phrases courtes qui claquent, bandeau pinceau, transitions à flou de mouvement). Univers : le flyer (noir, feu, pochoir).
# Les plats sont détourés depuis le flyer du client (.src/clean_cutouts.py). Effets de feu : assets/vendor/fire.js.
import os, json
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, TOTAL, OV = 1080, 1920, 36.5, 0.25
TOK = {'%COAL%': '#0B0908', '%CHAR%': '#17110D', '%FIRE%': '#F26A1B', '%EMBER%': '#FFB627', '%RED%': '#D7261E', '%BONE%': '#F4E9D8', '%GREEN%': '#1E6B3A'}
SC = [('01-accroche', 0.0, 3.6), ('02-brochette', 3.6, 4.8), ('03-menu', 8.4, 5.2), ('04-produits', 13.6, 7.4),
      ('05-accomp', 21.0, 4.0), ('06-boissons', 25.0, 3.6), ('07-halal', 28.6, 3.2), ('08-contact', 31.8, 4.7)]

FONTS = '''
    @font-face { font-family: "Anton"; src: url("assets/fonts/anton-latin-400-normal.woff2") format("woff2"); }
    @font-face { font-family: "Black Ops One"; src: url("assets/fonts/black-ops-one-latin-400-normal.woff2") format("woff2"); }
    @font-face { font-family: "Permanent Marker"; src: url("assets/fonts/permanent-marker-latin-400-normal.woff2") format("woff2"); }
    @font-face { font-family: "Oswald"; font-weight: 500; src: url("assets/fonts/oswald-latin-500-normal.woff2") format("woff2"); }
    @font-face { font-family: "Oswald"; font-weight: 700; src: url("assets/fonts/oswald-latin-700-normal.woff2") format("woff2"); }
'''
CSS = '''
    .X-a { position: absolute; }
    .X-c { left: 0; right: 0; text-align: center; }
    .X-full { position: absolute; inset: 0; }
    .X-cv { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }
    .X-h { font-family: "Anton"; color: %BONE%; text-transform: uppercase; line-height: 0.92; white-space: nowrap; letter-spacing: 0.005em; }
    .X-st { font-family: "Black Ops One"; color: %BONE%; line-height: 1; white-space: nowrap; }
    .X-gr { padding: 0.22em 0.04em; margin-top: -0.22em; -webkit-mask-image: url(assets/images/grunge.png); -webkit-mask-size: 640px 640px; mask-image: url(assets/images/grunge.png); mask-size: 640px 640px; }
    .X-mk { font-family: "Permanent Marker"; color: %BONE%; white-space: nowrap; }
    .X-in { font-family: "Oswald"; font-weight: 500; color: %BONE%; white-space: nowrap; letter-spacing: 0.04em; }
    .X-kick { font-family: "Oswald"; font-weight: 700; font-size: 32px; letter-spacing: 0.34em; color: %EMBER%; white-space: nowrap; text-transform: uppercase; }
    .X-coal { position: absolute; inset: 0; background: radial-gradient(70% 45% at 50% 62%, #2a140a 0%, %COAL% 70%); }
    .X-slate { position: absolute; inset: 0; background: url(assets/images/slate.jpg) center / cover; }
    .X-food { position: absolute; display: block; filter: drop-shadow(0 26px 30px rgba(0,0,0,0.55)); }
    .X-band { position: absolute; -webkit-mask: url(assets/images/brush.png) center / 100% 100% no-repeat; mask: url(assets/images/brush.png) center / 100% 100% no-repeat; }
    .X-band span { position: absolute; inset: 0; display: flex; justify-content: center; align-items: center; white-space: nowrap; }
    .X-m { position: absolute; overflow: hidden; box-sizing: content-box; padding-top: 70px; margin-top: -70px; }
    .X-m > * { display: inline-block; }
'''
def canv(*ids): return ''.join(f'    <canvas class="X-cv" id="X-{i}" width="1080" height="1920"></canvas>\n' for i in ids)
def fire_js(dur, emb=None, fl=None, sp=None):
    """Drive fire canvases from one proxy tween (seek-safe)."""
    lines, calls = [], []
    if emb: lines.append(f'      const __e = FG.embers(R("#X-emb"), {emb});'); calls.append('__e(__f.t)')
    if fl: lines.append(f'      const __l = FG.flames(R("#X-fl"), {fl});'); calls.append('__l(__f.t)')
    if sp: lines.append(f'      const __s = FG.sparks(R("#X-sp"), {sp});'); calls.append('__s(__f.t)')
    c = '; '.join(calls)
    return '\n'.join(lines) + f'''
      const __f = {{ t: 0 }};
      tl.fromTo(__f, {{ t: 0 }}, {{ t: {dur}, duration: {dur}, ease: "none", onUpdate: () => {{ {c}; }} }}, 0);
      {c};
'''
def slam(sel, at, frm=1.8, blur=14, d=0.32):
    return f'      tl.fromTo(R("{sel}"), {{ opacity: 0, scale: {frm}, filter: "blur({blur}px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: {d}, ease: "expo.out" }}, {at});\n'
def shake(at, k=1.0):
    return f'      tl.fromTo(R("#X-shk"), {{ x: {-16 * k:.0f}, y: {10 * k:.0f} }}, {{ x: 0, y: 0, duration: 0.45, ease: "elastic.out(1.2, 0.3)", immediateRender: false }}, {at});\n'
def up(sel, at, d=0.5, y=30):
    return f'      tl.fromTo(R("{sel}"), {{ opacity: 0, y: {y} }}, {{ opacity: 1, y: 0, duration: {d}, ease: "power3.out" }}, {at});\n'
def mask(sel, at, d=0.45):
    return f'      tl.fromTo(R("{sel}"), {{ yPercent: 105 }}, {{ yPercent: 0, duration: {d}, ease: "power4.out" }}, {at});\n'
def band(bid, x, y, w, h, color, text_html, txt_css):
    return f'    <div class="X-band" id="{bid}" style="left:{x}px; top:{y}px; width:{w}px; height:{h}px; background:{color}"><span style="{txt_css}">{text_html}</span></div>\n'
def band_in(bid, at, d=0.42):
    return (f'      tl.fromTo(R("#{bid}"), {{ clipPath: "inset(0 100% 0 0)" }}, {{ clipPath: "inset(0 0% 0 0)", duration: {d}, ease: "power3.inOut" }}, {at});\n' +
            slam(f'#{bid} span', round(at + d * 0.6, 2), 1.6, 10, 0.3))
def food(fid, img, x, y, w, extra=''):
    return f'    <img class="X-food" id="{fid}" src="assets/images/food/{img}.png" alt="" style="left:{x}px; top:{y}px; width:{w}px; {extra}">\n'

F = {}
# ── 01 · hook: ça grille à Ivry ────────────────────────────────────────────
F['01-accroche'] = ('', '''    <div class="X-coal"></div>
''' + canv('fl', 'emb') + '''    <div id="X-shk" class="X-full">
      <div class="X-a X-kick X-c" id="X-k" style="top:600px">Founerou Grill's · Ivry</div>
      <div class="X-a X-c X-h X-gr" id="X-l1" data-layout-allow-overlap style="top:670px; font-size:250px">Ça grille</div>
      <div class="X-a X-c X-h X-gr" id="X-l2" data-layout-allow-overlap style="top:930px; font-size:250px; color:%FIRE%">à Ivry !</div>
      <div class="X-a X-c X-mk" id="X-l3" style="top:1205px; font-size:74px; color:%EMBER%; transform: rotate(-4deg)">jusqu'à 2h du mat'</div>
    </div>
''', fire_js(3.9, emb='{ n: 110, seed: 3, alpha: 0.95 }', fl='{ y: 1960, height: 760, n: 260, size: 110, alpha: 0.17, seed: 5 }') +
 '      tl.fromTo(R("#X-k"), { opacity: 0 }, { opacity: 1, duration: 0.4 }, 0.05);\n' +
 slam('#X-l1', 0.35) + shake(0.4) + slam('#X-l2', 0.95) + shake(1.0, 1.2) +
 '      tl.fromTo(R("#X-l3"), { opacity: 0, scale: 0.6, rotation: -14 }, { opacity: 1, scale: 1, rotation: -4, duration: 0.45, ease: "back.out(2.2)" }, 1.6);\n' +
 '      tl.to([R("#X-k"), R("#X-l1"), R("#X-l2"), R("#X-l3")], { y: -260, opacity: 0, filter: "blur(16px)", duration: 0.32, ease: "power3.in", stagger: 0.03 }, 3.3);\n')

# ── 02 · brochette 1€ ─────────────────────────────────────────────────────
F['02-brochette'] = ('''
    #X-glow { position: absolute; left: -100px; right: -100px; top: 520px; height: 900px; background: radial-gradient(50% 50% at 50% 50%, rgba(242,106,27,0.42), rgba(215,38,30,0.12) 55%, rgba(0,0,0,0) 75%); }
    #X-eur { top: 1130px; font-size: 520px; color: %FIRE%; text-shadow: 0 0 60px rgba(242,106,27,0.55); }
''', '''    <div class="X-slate"></div>
    <div class="X-full" style="background:linear-gradient(180deg, rgba(11,9,8,0.75), rgba(11,9,8,0.2) 40%, rgba(11,9,8,0.85))"></div>
    <div id="X-glow"></div>
''' + canv('fl', 'emb') + '''    <div id="X-shk" class="X-full">
      <div class="X-a X-kick X-c" id="X-k" style="top:250px">Notre offre</div>
      <div class="X-a X-c X-m" style="top:300px; height:230px"><span class="X-h X-gr" id="X-t" style="font-size:215px">Brochette</span></div>
''' + food('X-hero', 'brochettes', 40, 600, 1000) + '''      <div class="X-a X-c X-st X-gr" id="X-eur" data-layout-allow-overlap>1€</div>
      <div class="X-a X-mk" id="X-only" data-layout-allow-overlap style="left:640px; top:1170px; font-size:68px; color:%BONE%; transform: rotate(-8deg)">seulement !</div>
      <div class="X-a X-c X-in" id="X-sub" style="top:1745px; font-size:40px; opacity:0.9">Poulet grillé · poivrons · oignons</div>
    </div>
''' + canv('sp'), fire_js(5.1, emb='{ n: 80, seed: 8 }', fl='{ y: 1990, height: 520, n: 180, size: 100, alpha: 0.13, seed: 2 }', sp='{ x: 540, y: 1400, t0: 1.5, n: 90, seed: 4 }') +
 '      tl.fromTo(R("#X-k"), { opacity: 0 }, { opacity: 1, duration: 0.3 }, 0.2);\n' + mask('#X-t', 0.25) +
 '      tl.fromTo(R("#X-hero"), { x: 1250, rotation: -20, filter: "blur(18px) drop-shadow(0 26px 30px rgba(0,0,0,0.55))" }, { x: 0, rotation: -7, filter: "blur(0px) drop-shadow(0 26px 30px rgba(0,0,0,0.55))", duration: 0.6, ease: "power3.out" }, 0.45);\n'
 '      tl.to(R("#X-hero"), { y: -18, rotation: -5, scale: 1.04, duration: 4.0, ease: "sine.inOut" }, 1.05);\n'
 '      tl.fromTo(R("#X-glow"), { opacity: 0.4 }, { opacity: 1, duration: 0.25, yoyo: true, repeat: 7, ease: "sine.inOut" }, 0.4);\n' +
 slam('#X-eur', 1.5, 2.6, 18, 0.34) + shake(1.52, 1.4) +
 '      tl.fromTo(R("#X-only"), { opacity: 0, scale: 0.5, rotation: -20 }, { opacity: 1, scale: 1, rotation: -8, duration: 0.45, ease: "back.out(2.4)" }, 1.95);\n' +
 up('#X-sub', 2.3, 0.5, 20) +
 '      tl.to(R("#X-shk"), { x: -1100, filter: "blur(18px)", duration: 0.3, ease: "power3.in" }, 4.55);\n')

# ── 03 · menu 6€90 (flat-lay on fire orange) ─────────────────────────────
CAN = '''<div class="X-a" id="X-can" style="left:742px; top:520px; width:200px; height:360px">
        <div style="position:absolute; left:0; top:18px; width:200px; height:330px; border-radius:26px 26px 30px 30px; background:linear-gradient(90deg, #5e0906 0%, %RED% 22%, #ff5a3c 40%, %RED% 62%, #4a0705 100%); box-shadow: 0 26px 30px rgba(0,0,0,0.4)"></div>
        <div style="position:absolute; left:10px; top:0; width:180px; height:34px; border-radius:50%; background:linear-gradient(180deg,#e8e8e8,#8d8d8d)"></div>
        <div style="position:absolute; left:0; right:0; top:150px; text-align:center; font-family:Anton; font-size:64px; color:%BONE%; letter-spacing:0.02em">33CL</div>
        <div style="position:absolute; left:0; right:0; top:230px; text-align:center; font-family:Oswald; font-weight:700; font-size:24px; letter-spacing:0.3em; color:%BONE%; opacity:0.85">BOISSON</div>
      </div>'''
F['03-menu'] = ('''
    #X-bg { position: absolute; inset: 0; background: radial-gradient(70% 50% at 50% 45%, #ff8a3d 0%, %FIRE% 55%, #c84b0c 100%); }
    .X-plus { font-family: "Anton"; font-size: 120px; color: %COAL%; }
    .X-f { font-family: "Oswald"; font-weight: 700; font-size: 46px; color: %COAL%; letter-spacing: 0.03em; white-space: nowrap; }
''', '''    <div id="X-bg"></div>
    <div id="X-shk" class="X-full">
      <div class="X-a X-c X-m" style="top:150px; height:300px"><span class="X-h X-gr" id="X-t" style="font-size:290px; color:%COAL%">Menu</span></div>
''' + food('X-pil', 'pilons', 70, 560, 560) + food('X-riz', 'riz', 300, 820, 470) + '      ' + CAN + '''
      <div class="X-a X-plus" id="X-p1" style="left:640px; top:600px">+</div>
      <div class="X-a X-plus" id="X-p2" style="left:180px; top:900px">+</div>
      <div class="X-a X-c" style="top:1250px; display:flex; flex-direction:column; align-items:center; gap:6px">
        <div class="X-f" id="X-f1">1 CUISSE OU 3 PILONS</div>
        <div class="X-f" id="X-f2">+ 1 ACCOMPAGNEMENT</div>
        <div class="X-f" id="X-f3">+ 1 BOISSON 33CL</div>
      </div>
''' + band('X-pr', 90, 1470, 900, 250, '%COAL%', '6€90', 'font-family:\'Black Ops One\'; font-size:190px; color:%FIRE%') + '''    </div>
''', slam('#X-t', 0.12, 1.6) + shake(0.15, 0.8) +
 '      tl.fromTo(R("#X-pil"), { x: -900, rotation: -25 }, { x: 0, rotation: -6, duration: 0.55, ease: "power3.out" }, 0.45);\n'
 '      tl.fromTo(R("#X-riz"), { y: 1200, rotation: 20 }, { y: 0, rotation: 4, duration: 0.55, ease: "power3.out" }, 0.75);\n'
 '      tl.fromTo(R("#X-can"), { x: 700, rotation: 30 }, { x: 0, rotation: 8, duration: 0.55, ease: "power3.out" }, 1.05);\n'
 '      ["#X-pil", "#X-riz", "#X-can"].forEach((s, i) => tl.to(R(s), { y: "+=" + (i % 2 ? -14 : 14), rotation: "+=2", duration: 3.2, ease: "sine.inOut" }, 1.6));\n'
 '      tl.fromTo([R("#X-p1"), R("#X-p2")], { scale: 0, rotation: -90 }, { scale: 1, rotation: 0, duration: 0.35, ease: "back.out(3)", stagger: 0.25 }, 1.2);\n' +
 up('#X-f1', 1.55, 0.35, 24) + up('#X-f2', 1.75, 0.35, 24) + up('#X-f3', 1.95, 0.35, 24) +
 band_in('X-pr', 2.45) + shake(2.75, 1.3) +
 '      tl.to(R("#X-shk"), { y: -1500, filter: "blur(18px)", duration: 0.3, ease: "power3.in" }, 4.95);\n')

# ── 04 · nos produits: one per beat, prices on the brush ─────────────────
PROD = [('poulet', '1 POULET', '8€'), ('demi-poulet', '1/2 POULET', '4€'), ('cuisse', '1 CUISSE', '2€'), ('pilons', '3 PILONS', '3€'),
        ('ailes', '4 AILES', '2€50'), ('saucisse', '1 SAUCISSE', '2€'), ('brick', '1 BRICK', '2€50'), ('donuts', '1 DONUTS', '2€50')]
items = ''
for i, (img, name, price) in enumerate(PROD):
    items += f'''    <div class="X-it" id="X-i{i}">
      <img class="X-food" src="assets/images/food/{img}.png" alt="" style="left:140px; top:640px; width:800px">
      <div class="X-a X-c X-h" style="top:1150px; font-size:140px">{name}</div>
''' + band(f'X-b{i}', 230, 1340, 620, 190, '%FIRE%', price.replace('€', '<small>€</small>'), 'font-family:\'Black Ops One\'; font-size:150px; color:%COAL%').replace('    <div class="X-band"', '      <div class="X-band"') + '    </div>\n'
p_js = ''
for i in range(len(PROD)):
    t0 = round(0.55 + i * 0.8, 2); side = 1 if i % 2 == 0 else -1
    p_js += f'      tl.fromTo(R("#X-i{i}"), {{ opacity: 1, x: {1150 * side}, rotation: {9 * side}, filter: "blur(22px)" }}, {{ x: 0, rotation: 0, filter: "blur(0px)", duration: 0.24, ease: "power3.out", immediateRender: false }}, {t0});\n'
    p_js += f'      tl.set(R("#X-i{i}"), {{ opacity: 1 }}, {t0});\n'
    p_js += band_in(f'X-b{i}', round(t0 + 0.04, 2), 0.16)
    p_js += f'      tl.set(R("#X-n"), {{ textContent: "{i + 1}/8" }}, {t0});\n'
    if i < len(PROD) - 1:
        p_js += f'      tl.to(R("#X-i{i}"), {{ x: {-1150 * side}, rotation: {-9 * side}, filter: "blur(22px)", duration: 0.18, ease: "power3.in" }}, {round(t0 + 0.62, 2)});\n'
        p_js += f'      tl.set(R("#X-i{i}"), {{ opacity: 0 }}, {round(t0 + 0.8, 2)});\n'
F['04-produits'] = ('''
    .X-it { position: absolute; inset: 0; opacity: 0; }
    .X-band small { font-size: 0.55em; vertical-align: 0.55em; }
''', '''    <div class="X-coal"></div>
''' + canv('fl', 'emb') + '''    <div id="X-shk" class="X-full">
      <div class="X-a X-c X-m" style="top:230px; height:200px"><span class="X-h X-gr" id="X-t" style="font-size:180px">Nos produits</span></div>
      <div class="X-a X-c X-mk" id="X-s" style="top:440px; font-size:60px; color:%FIRE%; transform: rotate(-3deg)">tout droit du grill</div>
      <div class="X-a X-in" id="X-n" style="right:70px; top:1650px; font-size:40px; opacity:0.7">1/8</div>
''' + items + '''    </div>
''', fire_js(7.7, emb='{ n: 90, seed: 11 }', fl='{ y: 2000, height: 480, n: 170, size: 95, alpha: 0.12, seed: 7 }') +
 mask('#X-t', 0.1) + '      tl.fromTo(R("#X-s"), { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(2)" }, 0.35);\n' +
 '      tl.fromTo(R("#X-n"), { opacity: 0 }, { opacity: 0.7, duration: 0.3 }, 0.55);\n' + p_js +
 '      tl.to(R("#X-shk"), { x: 1100, filter: "blur(18px)", duration: 0.28, ease: "power3.in" }, 7.12);\n')

# ── 05 · accompagnements (top-down slate, ref A drift) ───────────────────
ACC = [('pates', 'PÂTES<br>AU POULET', 70, 360, 560, 420), ('riz', 'RIZ<br>THAÏ', 570, 700, 90, 760), ('alloco', 'ALLOCO', 70, 1040, 560, 1130)]
acc_h, acc_j = '', ''
for i, (img, lab, x, y, lx, ly) in enumerate(ACC):
    acc_h += food(f'X-w{i}', img, x, y, 440) + f'      <div class="X-a X-h" id="X-lb{i}" style="left:{lx}px; top:{ly}px; font-size:92px; text-align:{"left" if lx > 300 else "right"}; width:420px">{lab}</div>\n'
    side = -1 if x < 300 else 1
    acc_j += f'      tl.fromTo(R("#X-w{i}"), {{ x: {900 * side}, rotation: {40 * side} }}, {{ x: 0, rotation: {6 * side}, duration: 0.6, ease: "power3.out" }}, {0.35 + i * 0.3:.2f});\n'
    acc_j += f'      tl.to(R("#X-w{i}"), {{ rotation: {-4 * side}, y: {-12 if i % 2 else 12}, duration: 3.0, ease: "sine.inOut" }}, {0.95 + i * 0.3:.2f});\n'
    acc_j += up(f'#X-lb{i}', round(0.6 + i * 0.3, 2), 0.4, 26)
F['05-accomp'] = ('', '''    <div class="X-slate"></div>
    <div class="X-full" style="background:radial-gradient(80% 60% at 50% 50%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.6) 100%)"></div>
    <div id="X-shk" class="X-full">
      <div class="X-a X-c X-m" style="top:170px; height:150px"><span class="X-h X-gr" id="X-t" style="font-size:132px; color:%FIRE%">Accompagnements</span></div>
''' + acc_h.replace('    <img', '      <img') + band('X-pr', 80, 1430, 920, 230, '%FIRE%', '3€ <em style=\'font-style:normal; font-size:0.6em; margin-left:18px\'>LA BARQUETTE</em>', 'font-family:Anton; font-size:150px; color:%COAL%').replace('    <div class="X-band"', '      <div class="X-band"') + '''    </div>
''', mask('#X-t', 0.1) + acc_j + band_in('X-pr', 1.6) + shake(1.85, 1.1) +
 '      tl.to(R("#X-shk"), { y: 1500, filter: "blur(18px)", duration: 0.28, ease: "power3.in" }, 3.72);\n')

# ── 06 · boissons ──────────────────────────────────────────────────────────
F['06-boissons'] = ('''
    #X-bg { position: absolute; inset: 0; background: radial-gradient(75% 55% at 50% 45%, #8e1510 0%, #4a0907 55%, #1c0403 100%); }
    .X-lab { font-family: "Oswald"; font-weight: 700; font-size: 44px; color: %EMBER%; letter-spacing: 0.06em; }
    #X-chip { position: absolute; left: 190px; top: 1560px; width: 700px; height: 110px; border-radius: 55px; background: rgba(11,9,8,0.75); border: 3px solid %FIRE%; display: flex; justify-content: center; align-items: center; font-family: Anton; font-size: 60px; color: %BONE%; letter-spacing: 0.02em; }
''', '''    <div id="X-bg"></div>
''' + canv('emb') + '''    <div id="X-shk" class="X-full">
      <div class="X-a X-c X-m" style="top:200px; height:210px"><span class="X-h X-gr" id="X-t" style="font-size:190px">À boire</span></div>
''' + food('X-bis', 'bissap', 150, 520, 330) + food('X-gin', 'gingembre', 690, 470, 200) + '''      <div class="X-a X-h" id="X-n1" style="left:60px; top:1080px; width:520px; text-align:center; font-size:96px">Bissap</div>
      <div class="X-a X-lab" id="X-p1" style="left:60px; top:1200px; width:520px; text-align:center">25CL · 2€50</div>
      <div class="X-a X-h" id="X-n2" style="left:520px; top:1080px; width:520px; text-align:center; font-size:96px">Gingembre</div>
      <div class="X-a X-lab" id="X-p2" style="left:520px; top:1200px; width:520px; text-align:center">25CL · 2€50</div>
      <div id="X-chip">BOISSON 33CL · 1€50</div>
    </div>
''', fire_js(3.9, emb='{ n: 70, seed: 15, alpha: 0.8 }') + mask('#X-t', 0.1) +
 '      tl.fromTo(R("#X-bis"), { y: -1300 }, { y: 0, duration: 0.7, ease: "bounce.out" }, 0.3);\n'
 '      tl.fromTo(R("#X-gin"), { y: -1300 }, { y: 0, duration: 0.7, ease: "bounce.out" }, 0.5);\n' +
 up('#X-n1', 0.95, 0.4) + up('#X-p1', 1.1, 0.4) + up('#X-n2', 1.15, 0.4) + up('#X-p2', 1.3, 0.4) +
 '      tl.fromTo(R("#X-chip"), { opacity: 0, scaleX: 0.4 }, { opacity: 1, scaleX: 1, duration: 0.45, ease: "back.out(1.8)" }, 1.7);\n'
 '      tl.to([R("#X-bis"), R("#X-gin")], { y: -10, duration: 1.4, ease: "sine.inOut", yoyo: true, repeat: 1 }, 1.0);\n'
 '      tl.to(R("#X-shk"), { scale: 1.6, opacity: 0, filter: "blur(16px)", duration: 0.3, ease: "power3.in" }, 3.32);\n')

# ── 07 · halal + horaires ────────────────────────────────────────────────
F['07-halal'] = ('''
    #X-ring { position: absolute; left: 320px; top: 250px; width: 440px; height: 440px; border-radius: 50%; box-shadow: 0 0 90px rgba(30,107,58,0.6); }
''', '''    <div class="X-coal"></div>
''' + canv('emb') + '''    <div id="X-shk" class="X-full">
      <div id="X-ring"></div>
''' + food('X-hal', 'halal', 340, 270, 400, 'border-radius:50%') + '''      <div class="X-a X-c X-h" id="X-t1" style="top:760px; font-size:120px">Certifié halal</div>
      <div class="X-a" id="X-rule" style="left:390px; top:910px; width:300px; height:6px; background:%FIRE%"></div>
      <div class="X-a X-c X-h X-gr" id="X-t2" style="top:960px; font-size:190px; color:%FIRE%">Ouvert 7j/7</div>
      <div class="X-a X-c X-h" id="X-t3" style="top:1170px; font-size:150px">de 11h à 2h</div>
      <div class="X-a X-c X-mk" id="X-t4" style="top:1370px; font-size:66px; color:%EMBER%; transform: rotate(-4deg)">même tard le soir !</div>
    </div>
''', fire_js(3.5, emb='{ n: 80, seed: 17 }') +
 '      tl.fromTo(R("#X-hal"), { rotationY: 200, scale: 0.4, opacity: 0 }, { rotationY: 0, scale: 1, opacity: 1, duration: 0.7, ease: "back.out(1.6)" }, 0.1);\n'
 '      tl.fromTo(R("#X-ring"), { opacity: 0 }, { opacity: 1, duration: 0.5 }, 0.5);\n' +
 up('#X-t1', 0.55, 0.4) + '      tl.fromTo(R("#X-rule"), { scaleX: 0 }, { scaleX: 1, duration: 0.4, ease: "power2.inOut" }, 0.8);\n' +
 slam('#X-t2', 1.0, 1.7) + shake(1.05, 1.0) + up('#X-t3', 1.35, 0.4) +
 '      tl.fromTo(R("#X-t4"), { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.4, ease: "back.out(2.2)" }, 1.8);\n'
 '      tl.to(R("#X-shk"), { y: -1500, filter: "blur(18px)", duration: 0.28, ease: "power3.in" }, 2.95);\n')

# ── 08 · contact ─────────────────────────────────────────────────────────
F['08-contact'] = ('''
    #X-frame { position: absolute; left: 90px; top: 300px; width: 900px; height: 460px; border: 4px solid rgba(244,233,216,0.85); }
    #X-frame i { position: absolute; left: 50%; top: -24px; width: 220px; height: 44px; margin-left: -110px; background: %COAL%; }
    .X-ad { font-family: "Oswald"; font-weight: 500; color: %BONE%; letter-spacing: 0.06em; }
''', '''    <div class="X-coal"></div>
''' + canv('fl', 'emb') + '''    <div id="X-shk" class="X-full">
      <div id="X-frame"><i></i></div>
      <div class="X-a X-c X-st X-gr" id="X-b1" style="top:360px; font-size:150px">FOUNEROU</div>
      <div class="X-a X-c X-st X-gr" id="X-b2" style="top:530px; font-size:180px; color:%FIRE%">GRILL'S</div>
      <div class="X-a X-c X-ad" id="X-a1" style="top:860px; font-size:54px">72 BD DE BRANDEBOURG</div>
      <div class="X-a X-c X-ad" id="X-a2" style="top:940px; font-size:46px; opacity:0.85">94200 IVRY-SUR-SEINE</div>
''' + band('X-tel', 20, 1060, 1040, 250, '%FIRE%', '01 49 87 07 96', 'font-family:Anton; font-size:112px; color:%COAL%; letter-spacing:0.03em') + '''      <div class="X-a X-c X-in" id="X-h" style="top:1360px; font-size:44px; color:%EMBER%">OUVERT 7J/7 · 11H – 2H · HALAL</div>
    </div>
''', fire_js(4.7, emb='{ n: 120, seed: 21 }', fl='{ y: 1990, height: 820, n: 280, size: 120, alpha: 0.19, seed: 9 }') +
 '      tl.fromTo(R("#X-frame"), { opacity: 0, scale: 1.15 }, { opacity: 1, scale: 1, duration: 0.5, ease: "power3.out" }, 0.1);\n' +
 slam('#X-b1', 0.2, 1.7) + slam('#X-b2', 0.45, 1.9) + shake(0.5, 1.2) +
 '      tl.fromTo([R("#X-b1"), R("#X-b2")], { opacity: 0.55 }, { opacity: 1, duration: 0.06, repeat: 5, yoyo: true, ease: "none", immediateRender: false }, 0.8);\n' +
 up('#X-a1', 1.0, 0.4) + up('#X-a2', 1.15, 0.4) + band_in('X-tel', 1.4, 0.45) + shake(1.7, 1.3) + up('#X-h', 1.95, 0.4, 20) +
 '      tl.fromTo(R("#X-tel span"), { scale: 1 }, { scale: 1.04, duration: 0.42, ease: "sine.inOut", yoyo: true, repeat: 3, immediateRender: false }, 2.5);\n')

def frame(fid, dur, css, html, js):
    pre = 'f' + fid[:2]
    def sub(s):
        s = s.replace('X-', pre + '-')
        for k, v in TOK.items(): s = s.replace(k, v)
        return s
    return f'''<template>
  <style>
{FONTS}
    #root {{ position: absolute; inset: 0; width: 100%; height: 100%; overflow: hidden; background: {TOK['%COAL%']}; }}
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
{sub(js)}
      tl.to({{}}, {{ duration: {dur} }}, 0);
      window.__timelines["{fid}"] = tl;
    }})();
  </script>
</template>
'''

os.makedirs(f'{P}/compositions/frames', exist_ok=True)
scenes, trans = '', ''
for i, (fid, st, ln) in enumerate(SC):
    css, html, js = F[fid]
    dur = round(ln + (OV if i < len(SC) - 1 else 0), 2)
    open(f'{P}/compositions/frames/{fid}.html', 'w').write(frame(fid, dur, css, html, js))
    scenes += f'      <div id="el-{fid}" class="scene" data-composition-id="{fid}" data-composition-src="compositions/frames/{fid}.html" data-start="{st}" data-duration="{dur}" data-track-index="{i % 2}"></div>\n'
    if i > 0:
        trans += f'        tl.fromTo("#el-{fid}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.12, ease: "none" }}, {st});\n'
# sound design: (file, start, volume)
SFX = [('sizzle', 0.0, 0.5), ('impact', 0.35, 0.55), ('impact', 0.95, 0.6),
       ('whoosh', 3.45, 0.5), ('riser', 3.75, 0.45), ('impact', 5.1, 0.75), ('sizzle', 4.3, 0.35),
       ('whoosh', 8.25, 0.5), ('impact', 8.55, 0.45), ('impact', 11.2, 0.7),
       ('whoosh', 13.45, 0.5)] + [('whoosh', round(13.6 + 0.55 + i * 0.8, 2), 0.28) for i in range(1, 8)] + [
       ('whoosh', 20.85, 0.5), ('impact', 22.85, 0.6), ('whoosh', 24.85, 0.45), ('whoosh', 28.45, 0.45), ('impact', 29.65, 0.55),
       ('whoosh', 31.65, 0.5), ('riser', 30.6, 0.4), ('impact', 32.25, 0.7), ('impact', 33.5, 0.75), ('sizzle', 33.6, 0.35)]
import soundfile as _sf
LEN = {n: round(_sf.info(f'{P}/assets/{n}.wav').duration, 2) for n in ('whoosh', 'impact', 'sizzle', 'riser')}
sfx = ''.join(f'      <audio id="sfx{i}" src="assets/{f}.wav" data-start="{t}" data-duration="{LEN[f]}" data-track-index="{20 + i % 6}" data-volume="{v}"></audio>\n' for i, (f, t, v) in enumerate(SFX))
VOJ = f'{P}/assets/voice/voice.json'
voice = os.path.exists(VOJ)
vo = ''.join(f'      <audio id="vo{i}" src="{s}" data-start="{a}" data-duration="{d}" data-track-index="{30 + i}" data-volume="1"></audio>\n' for i, (s, a, d) in enumerate(json.load(open(VOJ)))) if voice else ''
idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/fire.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #0B0908; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #0B0908; }}
      .scene {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
{scenes}
      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="15" data-volume="{0.35 if voice else 0.8}"></audio>
{sfx}{vo}    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
      (function () {{ var tl = window.__timelines["main"];
{trans}        tl.to({{}}, {{ duration: {TOTAL} }}, 0);
      }})();
    </script>
  </body>
</html>
'''
open(f'{P}/index.html', 'w').write(idx)
print('ok')
