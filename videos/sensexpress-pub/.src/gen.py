# SensExpress — publicité produit 40 s, vertical 1080×1920, 25 i/s. Photos réelles du catalogue SensExpress.
import os, json
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, TOTAL, OV = 1080, 1920, 40, 0.6
SC = [('01-accroche', 0, 4.5), ('02-sentir', 4.5, 5.5), ('03-heritier', 10, 6), ('04-collection', 16, 8), ('05-parfums', 24, 6), ('06-espaces', 30, 4), ('07-contact', 34, 6)]

FONTS = '''
    @font-face { font-family: "Playfair Display"; font-weight: 400; src: url("assets/fonts/playfair-display-latin-400-normal.woff2") format("woff2"); }
    @font-face { font-family: "Playfair Display"; font-weight: 600; src: url("assets/fonts/playfair-display-latin-600-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 400; src: url("assets/fonts/montserrat-latin-400-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 500; src: url("assets/fonts/montserrat-latin-500-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 600; src: url("assets/fonts/montserrat-latin-600-normal.woff2") format("woff2"); }
'''
CSS = '''
    .X-a { position: absolute; }
    .X-full { position: absolute; inset: 0; }
    .X-cv { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }
    .X-bgd { position: absolute; inset: 0; background: radial-gradient(90% 60% at 50% 45%, #1d160a 0%, #0b0907 55%, #000 100%); }
    .X-kick { font-family: "Montserrat"; font-weight: 500; font-size: 24px; letter-spacing: 0.28em; color: #E9C221; white-space: nowrap; }
    .X-l1, .X-l2 { position: absolute; left: 120px; font-family: "Playfair Display"; font-weight: 600; font-size: 80px; line-height: 1.1; color: #FFFFFF; white-space: nowrap; }
    .X-l2 { color: #E9C221; }
    .X-c { left: 0; right: 0; text-align: center; }
    .X-ph { position: absolute; overflow: hidden; }
    .X-ph .b { position: absolute; inset: -50px; background-size: cover; background-position: center; filter: blur(30px) brightness(0.55) saturate(1.1); }
    .X-ph img { position: absolute; left: 0; top: 0; width: 100%; height: 100%; display: block; }
    .X-ph img.ct { object-fit: contain; }
    .X-ph img.cv { object-fit: cover; }
    .X-ln { position: absolute; inset: 0; pointer-events: none; border: 2px solid rgba(233,194,33,0.6); }
'''
def statement(l1, l2, y, kick=None, center=False):
    c = ' X-c' if center else ''
    k = f'    <div class="X-a X-kick{c}" id="X-k" style="{"" if center else "left:120px; "}top:{y - 52}px">{kick}</div>\n' if kick else ''
    return k + f'''    <div class="X-l1{c}" id="X-s1" style="top:{y}px">{l1}</div>
    <div class="X-l2{c}" id="X-s2" style="top:{y + 90}px">{l2}</div>
'''
def st_in(at, kick=False):
    k = f'      tl.fromTo(R("#X-k"), {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }}, {round(at - 0.15, 2)});\n' if kick else ''
    return k + f'''      tl.fromTo(R("#X-s1"), {{ opacity: 0, y: 34 }}, {{ opacity: 1, y: 0, duration: 0.7, ease: "power3.out" }}, {at});
      tl.fromTo(R("#X-s2"), {{ opacity: 0, y: 34 }}, {{ opacity: 1, y: 0, duration: 0.7, ease: "power3.out" }}, {round(at + 0.25, 2)});
'''
def fx(dur, mist=None, dust=True, dk=0.7):
    out = ''
    if dust: out += f'      const __d = SX.dust(R("#X-dust"), {{ n: 80, alpha: {dk}, seed: 5 }});\n'
    if mist: out += f'      const __m = SX.mist(R("#X-mist"), {mist});\n'
    calls = ('__d(__fs.t); ' if dust else '') + ('__m(__fs.t); ' if mist else '')
    return out + f'''      const __fs = {{ t: 0 }};
      tl.fromTo(__fs, {{ t: 0 }}, {{ t: {dur}, duration: {dur}, ease: "none", onUpdate: () => {{ {calls}}} }}, 0);
      {calls}
'''
CANV = '    <canvas class="X-cv" id="X-mist" width="1080" height="1920"></canvas>\n    <canvas class="X-cv" id="X-dust" width="1080" height="1920"></canvas>\n'
def photo(idn, img, x, y, w, h, radius, fit='ct', pos='center', blurbg=True, line=True):
    b = f'<div class="b" style="background-image:url(assets/images/{img})"></div>' if blurbg else ''
    ln = f'<div class="X-ln" style="border-radius:{radius}"></div>' if line else ''
    return f'<div class="X-ph" id="{idn}" style="left:{x}px; top:{y}px; width:{w}px; height:{h}px; border-radius:{radius}">{b}<img class="{fit}" id="{idn}i" src="assets/images/{img}" alt="" style="object-position:{pos}">{ln}</div>'

F = {}
# ── 01 · 0–4.5 s · the hook ───────────────────────────────────────────────
F['01-accroche'] = ('''
    .X-mk { position: absolute; left: 0; right: 0; overflow: hidden; text-align: center; height: 110px; }
    .X-mk span { display: inline-block; font-family: "Playfair Display"; font-weight: 600; font-size: 86px; line-height: 110px; color: #FFFFFF; white-space: nowrap; }
    #X-m2 span { color: #E9C221; }
    #X-sweep { position: absolute; left: -400px; top: 760px; width: 300px; height: 320px; background: linear-gradient(90deg, rgba(255,240,190,0), rgba(255,240,190,0.22), rgba(255,240,190,0)); transform: skewX(-18deg); }
''', '''    <div class="X-bgd"></div>
''' + CANV + '''    <div class="X-a X-kick X-c" id="X-k" style="top:770px">SENSEXPRESS · MARKETING OLFACTIF</div>
    <div class="X-mk" id="X-m1" style="top:815px"><span>Et si votre marque</span></div>
    <div class="X-mk" id="X-m2" style="top:925px"><span>avait un parfum ?</span></div>
    <div id="X-sweep"></div>
''', fx(5.1, '{ x: 540, y: 1700, spread: 300, rise: 1300, size: 110, alpha: 0.08, n: 44, seed: 9 }') + '''      tl.fromTo(R("#X-k"), { opacity: 0, scale: 1.06 }, { opacity: 1, scale: 1, duration: 1.0, ease: "power2.out" }, 0.2);
      tl.fromTo(R("#X-m1 span"), { yPercent: 110 }, { yPercent: 0, duration: 0.8, ease: "power3.out" }, 0.55);
      tl.fromTo(R("#X-m2 span"), { yPercent: 110 }, { yPercent: 0, duration: 0.8, ease: "power3.out" }, 1.05);
      tl.fromTo(R("#X-sweep"), { x: 0 }, { x: 1700, duration: 1.3, ease: "power2.inOut" }, 1.9);
      tl.to([R("#X-k"), R("#X-m1"), R("#X-m2")], { opacity: 0, filter: "blur(8px)", scale: 1.04, duration: 0.6, ease: "power2.in" }, 4.0);
''')
# ── 02 · 4.5–10 s · « faites sentir votre marque » + mood photos ─────────
MOOD = ['lavande', 'citron', 'coucher-soleil', 'fruits']
arches = ''.join('    ' + photo(f'X-w{i}', f'{m}.jpg', 120 + i * 215, 690 + (70 if i % 2 else 0), 195, 850, '98px 98px 18px 18px', 'cv', 'center', False) + '\n' for i, m in enumerate(MOOD))
F['02-sentir'] = ('''
    #X-p { position: absolute; left: 120px; right: 120px; top: 225px; font-family: "Montserrat"; font-weight: 400; font-size: 32px; line-height: 1.45; color: #BDBDBD; }
''', '''    <div class="X-full" style="background:linear-gradient(180deg,#000 0%,#0d0a06 100%)"></div>
    <div id="X-p">Ne vous contentez plus de faire parler<br>de vos produits :</div>
''' + statement('faites sentir', 'votre marque.', 345) + arches, '''      tl.fromTo(R("#X-p"), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, 0.45);
''' + st_in(2.85) + '''      [0, 1, 2, 3].forEach((i) => {
        tl.fromTo(R("#X-w" + i), { clipPath: "inset(100% 0% 0% 0%)", y: 60 }, { clipPath: "inset(0% 0% 0% 0%)", y: 0, duration: 0.9, ease: "power3.out" }, 0.45 + i * 0.18);
        tl.fromTo(R("#X-w" + i + "i"), { scale: 1.25 }, { scale: 1.02, duration: 5.6, ease: "power1.out" }, 0.45 + i * 0.18);
        tl.to(R("#X-w" + i), { y: i % 2 ? -50 : -20, duration: 5.0, ease: "none" }, 1.1);
      });
''')
# ── 03 · 10–16 s · L'Héritier, hero ──────────────────────────────────────
FEAT = ["Détection de mouvement", "Au bon moment, sans gaspillage", "Jusqu'à 3 semaines d'autonomie"]
feat = ''.join(f'    <div class="X-a X-c X-ft" id="X-f{i}"><i></i>{f}</div>\n' for i, f in enumerate(FEAT))
F['03-heritier'] = ('''
    .X-ft { top: 1455px; display: flex; justify-content: center; align-items: center; gap: 16px; font-family: "Montserrat"; font-weight: 500; font-size: 36px; color: #FFFFFF; opacity: 0; }
    .X-ft i { display: block; width: 12px; height: 12px; border-radius: 6px; background: #E9C221; }
    #X-hm { position: absolute; left: 160px; top: 390px; }
''', '''    <div class="X-bgd"></div>
    <canvas class="X-cv" id="X-dust" width="1080" height="1920"></canvas>
''' + statement("L'Héritier", '', 230, 'DIFFUSEUR INTELLIGENT', center=True).replace('font-size', 'font-size') + '''    ''' + photo('X-hero', 'heritier-brume.jpg', 160, 390, 760, 1010, '380px 380px 28px 28px', 'cv', '50% 30%', False).replace('style="object-position:50% 30%"', 'style="left:-40px; top:-235px; width:800px; height:1275px; object-fit:fill"') + '''
    <canvas id="X-hm" width="760" height="1010"></canvas>
''' + feat, fx(6.6, None) + '''      const hm = SX.mist(R("#X-hm"), { x: 474, y: 177, spread: 70, rise: 260, size: 40, alpha: 0.06, n: 24, seed: 4, gold: 0 });
      const hs = { t: 0 }; tl.fromTo(hs, { t: 0 }, { t: 6.6, duration: 6.6, ease: "none", onUpdate: () => hm(hs.t) }, 0); hm(0);
      tl.fromTo(R("#X-k"), { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, 0.3);
      tl.fromTo(R("#X-s1"), { opacity: 0, y: 34, scale: 1.04 }, { opacity: 1, y: 0, scale: 1, duration: 0.9, ease: "power3.out" }, 0.45);
      tl.fromTo(R("#X-hero"), { clipPath: "inset(100% 0% 0% 0% round 380px 380px 28px 28px)" }, { clipPath: "inset(0% 0% 0% 0% round 380px 380px 28px 28px)", duration: 1.0, ease: "power3.inOut" }, 0.2);
      tl.fromTo(R("#X-heroi"), { scale: 1.18 }, { scale: 1.0, duration: 6.4, ease: "power1.out" }, 0.2);
      [0, 1, 2].forEach((i) => {
        const FT = [1.3, 3.2, 4.9];
        tl.fromTo(R("#X-f" + i), { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" }, FT[i]);
        if (i < 2) tl.to(R("#X-f" + i), { opacity: 0, y: -20, duration: 0.35, ease: "power2.in" }, FT[i + 1] - 0.4);
      });
''')
# ── 04 · 16–24 s · the collection: one card per spoken name, then the line-up ──
PROD = [('princesse.jpg', 'La Princesse'), ('duchesse.jpg', 'La Duchesse'), ('prince.jpg', 'Le Prince'), ('reine.jpg', 'La Reine')]
cards = ''.join('    ' + photo(f'X-c{i}', img, 120, 520, 840, 800, '36px', 'ct') + '\n' for i, (img, n) in enumerate(PROD))
names = ''.join(f'    <div class="X-a X-c X-pn" id="X-n{i}"><b>{n}</b></div>\n' for i, (img, n) in enumerate(PROD))
# voice: names at 16.95 / 17.65 / 18.51 / 19.01, then « une collection pour chaque volume » at 20.3
AT4 = [0.9, 1.6, 2.46, 2.96]
CELL = [(330, 760), (750, 760), (330, 1165), (750, 1165)]
S4CSS = """
    .X-pn { top: 1360px; opacity: 0; }
    .X-pn b { display: block; font-family: "Playfair Display"; font-weight: 600; font-size: 84px; color: #E9C221; }
    #X-all { top: 1395px; font-family: "Montserrat"; font-weight: 500; font-size: 27px; letter-spacing: 0.08em; color: #E9C221; opacity: 0; }
"""
S4HTML = '    <div class="X-bgd"></div>\n' + statement('Une collection', 'pour chaque volume.', 200, 'LA COLLECTION') + cards + names + '    <div class="X-a X-c" id="X-all">La Princesse · La Duchesse · Le Prince · La Reine</div>\n'
S4JS = """      tl.fromTo(R("#X-k"), { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, 0.2);
      const AT = """ + json.dumps(AT4) + """, CELL = """ + json.dumps(CELL) + """;
      [0, 1, 2, 3].forEach((i) => {
        const c = R("#X-c" + i), n = R("#X-n" + i), t0 = AT[i];
        tl.fromTo(c, { x: 1100, rotation: 3 }, { x: 0, rotation: 0, duration: 0.42, ease: "power3.out" }, t0 - 0.12);
        tl.fromTo(R("#X-c" + i + "i"), { scale: 1.1 }, { scale: 1.0, duration: 1.4, ease: "power2.out" }, t0 - 0.12);
        tl.fromTo(n, { opacity: 0, y: 22 }, { opacity: 1, y: 0, duration: 0.28, ease: "power2.out" }, t0);
        if (i < 3) {
          tl.to(c, { x: -1100, rotation: -3, duration: 0.42, ease: "power3.in" }, AT[i + 1] - 0.12);
          tl.to(n, { opacity: 0, duration: 0.18 }, AT[i + 1] - 0.12);
        }
      });
      // the line-up on « une collection pour chaque volume »
      tl.to(R("#X-n3"), { opacity: 0, duration: 0.25 }, 3.95);
      [0, 1, 2, 3].forEach((i) => tl.fromTo(R("#X-c" + i), { x: i < 3 ? -1100 : 0, y: 0, scale: 1, rotation: 0 }, { x: CELL[i][0] - 540, y: CELL[i][1] - 920, scale: 0.476, rotation: 0, duration: 0.7, ease: "power3.inOut", immediateRender: false }, 4.0 + (i < 3 ? i * 0.07 : 0)));
""" + st_in(4.25) + """      tl.fromTo(R("#X-all"), { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }, 4.8);
"""
F['04-collection'] = (S4CSS, S4HTML, S4JS)
# ── 05 · 24–30 s · the fragrances ─────────────────────────────────────────
PARF = ['Anissa', 'Son Altesse', 'Prestige des rois', 'Vanille bourbon', 'Tropical paradise', 'Signature Royale']
slot = ''.join(f'    <div class="X-a X-c X-sn" id="X-sn{i}">{p}</div>\n' for i, p in enumerate(PARF))
F['05-parfums'] = ('''
    .X-sn { top: 1395px; font-family: "Playfair Display"; font-weight: 600; font-size: 74px; color: #E9C221; opacity: 0; white-space: nowrap; }
''', '''    <div class="X-bgd"></div>
''' + statement('Une signature', 'pour chaque lieu.', 200, 'NOS PARFUMS') + '    ' + photo('X-fam', 'heritier-famille.jpg', 120, 470, 840, 840, '36px', 'cv', 'center', False) + '''
    <div class="X-a X-kick X-c" id="X-six" style="top:1345px">SIX PARFUMS SIGNATURE</div>
''' + slot, st_in(0.2, kick=True) + '''      tl.fromTo(R("#X-fam"), { opacity: 0, y: 50 }, { opacity: 1, y: 0, duration: 0.8, ease: "power3.out" }, 0.3);
      tl.fromTo(R("#X-fami"), { scale: 1.0 }, { scale: 1.1, duration: 6.3, ease: "none" }, 0.3);
      tl.fromTo(R("#X-six"), { opacity: 0 }, { opacity: 1, duration: 0.5 }, 0.9);
      [0, 1, 2, 3, 4, 5].forEach((i) => {
        const el = R("#X-sn" + i), t0 = 1.1 + i * 0.78;
        tl.fromTo(el, { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.32, ease: "power3.out" }, t0);
        if (i < 5) tl.to(el, { opacity: 0, y: -40, duration: 0.28, ease: "power2.in" }, t0 + 0.55);
      });
''')
# ── 06 · 30–34 s · every space ────────────────────────────────────────────
ICONS = [
 '<path d="M 70 330 H 430 M 50 352 H 450 M 100 320 A 150 150 0 0 1 400 320 M 236 168 H 264 M 250 168 V 146 M 170 250 A 100 100 0 0 1 220 200"/>',
 '<path d="M 70 170 L 250 80 L 430 170 Z M 85 192 H 415 M 120 210 V 330 M 200 210 V 330 M 300 210 V 330 M 380 210 V 330 M 75 345 H 425 M 55 368 H 445"/>',
 '<path d="M 80 220 L 250 90 L 420 220 M 115 195 V 370 H 385 V 195 M 220 370 V 290 H 280 V 370 M 145 250 H 195 V 300 H 145 Z M 305 250 H 355 V 300 H 305 Z"/>',
 '<path d="M 50 320 H 85 A 40 40 0 0 1 165 320 H 335 A 40 40 0 0 1 415 320 H 455 V 280 Q 452 258 420 252 L 360 242 L 300 190 Q 286 178 262 178 H 160 Q 140 178 126 192 L 88 238 Q 52 246 50 270 Z M 125 320 m -28 0 a 28 28 0 1 0 56 0 a 28 28 0 1 0 -56 0 M 375 320 m -28 0 a 28 28 0 1 0 56 0 a 28 28 0 1 0 -56 0 M 120 242 L 160 200 H 228 V 242 Z M 248 242 V 200 H 285 L 330 242 Z"/>']
LBL = ['Hôtels', 'Bureaux', 'Maison', 'Voiture']
icons = ''.join(f'''    <div class="X-a X-ic" id="X-i{i}" style="left:{130 + i * 210}px"><svg width="190" height="190" viewBox="0 0 500 500"><g stroke="#E9C221" stroke-width="9" fill="none" stroke-linecap="round" stroke-linejoin="round">{p}</g></svg><span>{LBL[i]}</span></div>\n''' for i, p in enumerate(ICONS))
F['06-espaces'] = ('''
    .X-ic { top: 960px; width: 190px; text-align: center; }
    .X-ic svg { display: block; }
    .X-ic span { display: block; margin-top: 10px; font-family: "Montserrat"; font-weight: 500; font-size: 28px; letter-spacing: 0.12em; color: #FFFFFF; }
''', '''    <div class="X-bgd"></div>
''' + CANV + statement('Un parfum', 'pour chaque espace.', 690, 'HÔTELS · BUREAUX · MAISON · VOITURE', center=True) + icons,
 fx(4.6, '{ x: 540, y: 1750, spread: 340, rise: 1100, size: 100, alpha: 0.06, n: 36, seed: 13 }') + st_in(0.2, kick=True) + '''      [0, 1, 2, 3].forEach((i) => {
        const el = R("#X-i" + i);
        const IT = [0.72, 1.48, 2.16, 2.78];
        tl.fromTo(el, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" }, IT[i]);
        el.querySelectorAll("path").forEach((p) => { const L = p.getTotalLength(); tl.fromTo(p, { attr: { "stroke-dasharray": L, "stroke-dashoffset": L } }, { attr: { "stroke-dashoffset": 0 }, duration: 0.8, ease: "power2.inOut" }, IT[i] + 0.05); });
      });
''')
# ── 07 · 34–40 s · logo and contact ───────────────────────────────────────
F['07-contact'] = ('''
    #X-logo { position: absolute; left: 160px; top: 520px; width: 760px; height: 411px; }
    #X-logo img { display: block; width: 100%; }
    #X-url { top: 1080px; font-family: "Playfair Display"; font-weight: 600; font-size: 74px; color: #FFFFFF; }
    #X-url em { font-style: normal; color: #E9C221; }
    #X-tel { top: 1200px; font-family: "Montserrat"; font-weight: 600; font-size: 38px; color: #E9C221; }
    #X-pays { top: 1275px; font-family: "Montserrat"; font-weight: 500; font-size: 24px; letter-spacing: 0.2em; color: #BDBDBD; }
    #X-adr { top: 1325px; font-family: "Montserrat"; font-weight: 400; font-size: 26px; color: #9A9A9A; }
    #X-fil { top: 1040px; display: flex; justify-content: center; }
    #X-fil i { display: block; width: 180px; height: 2px; background: #E9C221; }
''', '''    <div class="X-full" style="background:#000"></div>
''' + CANV + '''    <div id="X-logo"><img src="assets/images/sensexpress-logo.png" alt="SensExpress"></div>
    <div class="X-a X-c" id="X-fil"><i></i></div>
    <div class="X-a X-c" id="X-url">sensexpress<em>.com</em></div>
    <div class="X-a X-c" id="X-tel">Mali · +223 70 28 07 07</div>
    <div class="X-a X-c" id="X-pays">MALI · BURKINA · SÉNÉGAL · CÔTE D'IVOIRE</div>
    <div class="X-a X-c" id="X-adr">Hamdallaye ACI, près du Bougie Ba</div>
''', fx(6.0, '{ x: 540, y: 1000, spread: 300, rise: 900, size: 110, alpha: 0.06, n: 40, seed: 17 }', True, 0.55) + '''      tl.fromTo(R("#X-logo"), { opacity: 0, scale: 0.94, filter: "blur(10px)" }, { opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.9, ease: "power2.out" }, 0.2);
      tl.fromTo(R("#X-fil i"), { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: "power2.inOut" }, 1.0);
      tl.fromTo(R("#X-url"), { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, 1.2);
      tl.fromTo(R("#X-tel"), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, 1.5);
      tl.fromTo(R("#X-pays"), { opacity: 0 }, { opacity: 1, duration: 0.6 }, 1.8);
      tl.fromTo(R("#X-adr"), { opacity: 0 }, { opacity: 1, duration: 0.6 }, 2.0);
''')

def frame(fid, dur, css, html, js):
    pre = 'p' + fid[:2]
    sub = lambda s: s.replace('X-', pre + '-')
    return f'''<template>
  <style>
{FONTS}
    #root {{ position: absolute; inset: 0; width: 100%; height: 100%; overflow: hidden; font-family: "Montserrat", sans-serif; color: #FFFFFF; background: #000; }}
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
scenes, trans = '', ''
for i, (fid, st, ln) in enumerate(SC):
    css, html, js = F[fid]
    dur = round(ln + (OV if i < len(SC) - 1 else 0), 2)
    open(f'{P}/compositions/frames/{fid}.html', 'w').write(frame(fid, dur, css, html, js))
    scenes += f'      <div id="el-{fid}" class="scene" data-composition-id="{fid}" data-composition-src="compositions/frames/{fid}.html" data-start="{st}" data-duration="{dur}" data-track-index="{i % 2}"></div>\n'
    if i > 0:
        trans += f'        tl.fromTo("#el-{fid}", {{ opacity: 0 }}, {{ opacity: 1, duration: {OV}, ease: "power2.inOut" }}, {st});\n'
br = ''.join(f'      <audio id="el-breath{i}" src="assets/breath.wav" data-start="{t}" data-duration="1.1" data-track-index="{12 + i}" data-volume="0.3"></audio>\n' for i, t in enumerate([4.1, 9.6, 23.6, 33.6]))
idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/sx.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
      .scene {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
{scenes}
      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="11" data-volume="0.6"></audio>
{br}    </div>
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
