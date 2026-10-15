# SensExpress — « Une signature qui se voit » — 42 s, master vertical 1080×1920, 25 i/s.
# Writes compositions/frames/*.html and index.html.
import os, json
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, TOTAL, OV = 1080, 1920, 42, 0.6
SC = [('01-signature', 0, 5), ('02-sens', 5, 7), ('03-univers', 12, 8), ('04-solutions', 20, 8), ('05-echange', 28, 8), ('06-adresse', 36, 6)]
GOLD = '#E9C221'

FONTS = '''
    @font-face { font-family: "Playfair Display"; font-weight: 400; src: url("assets/fonts/playfair-display-latin-400-normal.woff2") format("woff2"); }
    @font-face { font-family: "Playfair Display"; font-weight: 600; src: url("assets/fonts/playfair-display-latin-600-normal.woff2") format("woff2"); }
    @font-face { font-family: "Playfair Display"; font-weight: 700; src: url("assets/fonts/playfair-display-latin-700-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 400; src: url("assets/fonts/montserrat-latin-400-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 500; src: url("assets/fonts/montserrat-latin-500-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 600; src: url("assets/fonts/montserrat-latin-600-normal.woff2") format("woff2"); }
'''
CSS = '''
    .X-a { position: absolute; }
    .X-full { position: absolute; inset: 0; }
    .X-cv { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }
    .X-kick { font-family: "Montserrat"; font-weight: 500; font-size: 24px; letter-spacing: 0.26em; color: #E9C221; white-space: nowrap; }
    .X-l1, .X-l2 { position: absolute; left: 120px; font-family: "Playfair Display"; font-weight: 600; font-size: 76px; line-height: 1.1; color: #FFFFFF; white-space: nowrap; }
    .X-l2 { color: #E9C221; }
    /* ── site reconstruction (mobile home, 800 px wide) ── */
    .X-home { position: absolute; left: 0; top: 0; width: 800px; height: 1130px; background: #000; overflow: hidden; }
    .X-hd { height: 112px; display: flex; align-items: center; padding: 0 36px; background: #000; border-bottom: 1px solid #1d1d1d; }
    .X-hd img { display: block; height: 72px; }
    .X-bg { margin-left: auto; display: flex; flex-direction: column; gap: 9px; }
    .X-bg i { display: block; width: 40px; height: 3px; background: #FFFFFF; }
    .X-img { position: relative; height: 500px; overflow: hidden; background: radial-gradient(70% 70% at 62% 38%, #4a3712 0%, #1a1308 45%, #070605 100%); }
    .X-txtb { padding: 52px 48px 0; }
    .X-ttl { font-family: "Playfair Display"; font-weight: 600; font-size: 70px; line-height: 1.08; color: #FFFFFF; margin-top: 18px; }
    .X-ttl em { font-style: normal; color: #E9C221; }
    .X-p { font-family: "Montserrat"; font-weight: 400; font-size: 27px; line-height: 1.55; color: #C9C9C9; margin-top: 22px; }
    .X-btns { display: flex; flex-direction: column; gap: 18px; margin-top: 38px; }
    .X-btn { display: flex; align-items: center; justify-content: center; height: 78px; font-family: "Montserrat"; font-weight: 600; font-size: 22px; letter-spacing: 0.14em; color: #000; background: #E9C221; white-space: nowrap; }
    .X-btn.ol { color: #E9C221; background: transparent; border: 2px solid #E9C221; }
    /* arch windows */
    .X-arch { position: absolute; left: 180px; top: 470px; width: 720px; height: 1120px; border-radius: 360px 360px 28px 28px; overflow: hidden; border: 2px solid rgba(233,194,33,0.55); }
    .X-in { position: absolute; inset: 0; }
    .X-arch svg.ic { position: absolute; left: 110px; top: 250px; width: 500px; height: 500px; }
    .X-al { position: absolute; left: 50px; right: 50px; bottom: 70px; text-align: center; }
    .X-al span { display: block; font-family: "Montserrat"; font-weight: 500; font-size: 24px; letter-spacing: 0.26em; color: #E9C221; }
    .X-al b { display: block; margin-top: 16px; font-family: "Playfair Display"; font-weight: 600; font-size: 58px; line-height: 1.12; color: #FFFFFF; }
'''

def statement(l1, l2, y, kick=None):
    k = f'    <div class="X-a X-kick" id="X-k" style="left:120px; top:{y - 52}px">{kick}</div>\n' if kick else ''
    return k + f'''    <div class="X-l1" id="X-s1" style="top:{y}px">{l1}</div>
    <div class="X-l2" id="X-s2" style="top:{y + 86}px">{l2}</div>
'''
def st_in(at, kick=False):
    k = f'      tl.fromTo(R("#X-k"), {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }}, {at - 0.15});\n' if kick else ''
    return k + f'''      tl.fromTo(R("#X-s1"), {{ opacity: 0, y: 34 }}, {{ opacity: 1, y: 0, duration: 0.7, ease: "power3.out" }}, {at});
      tl.fromTo(R("#X-s2"), {{ opacity: 0, y: 34 }}, {{ opacity: 1, y: 0, duration: 0.7, ease: "power3.out" }}, {at + 0.25});
'''
def drive(expr, dur, var='__r'):
    return f'''      const {var} = {expr};
      const {var}s = {{ t: 0 }};
      tl.fromTo({var}s, {{ t: 0 }}, {{ t: {dur}, duration: {dur}, ease: "none", onUpdate: () => {var}({var}s.t) }}, 0);
      {var}(0);
'''

# hero image of the home page: an evocative interior in gold line-art (illustration, not a photo of the site)
HERO_SVG = '''<svg class="X-a" style="left:0;top:0" width="800" height="500" viewBox="0 0 800 500">
          <path d="M 470 470 V 170 A 120 120 0 0 1 710 170 V 470" stroke="rgba(233,194,33,0.35)" stroke-width="2" fill="rgba(233,194,33,0.05)"/>
          <path d="M 590 470 V 60" stroke="rgba(233,194,33,0.18)" stroke-width="2"/>
          <path d="M 60 400 H 420 M 90 400 V 470 M 390 400 V 470" stroke="rgba(233,194,33,0.55)" stroke-width="3" fill="none"/>
          <rect x="222" y="268" width="56" height="132" rx="26" fill="#0d0d0d" stroke="#E9C221" stroke-width="2"/>
          <rect x="222" y="372" width="56" height="7" fill="#E9C221"/>
          <path d="M 250 262 C 236 230 268 214 252 186 C 238 160 270 146 258 118" stroke="rgba(255,240,210,0.55)" stroke-width="3" fill="none" stroke-linecap="round"/>
          <path d="M 262 258 C 284 236 270 214 292 196" stroke="rgba(233,194,33,0.6)" stroke-width="2.5" fill="none" stroke-linecap="round"/>
        </svg>'''
def home(ids=True):
    i = (lambda s: f' id="{s}"') if ids else (lambda s: '')
    return f'''<div class="X-hd"{i('X-hhd')}><img src="assets/images/sensexpress-logo.png" alt="SensExpress"><div class="X-bg"><i></i><i></i><i></i></div></div>
        <div class="X-img"{i('X-himg')}>{HERO_SVG}</div>
        <div class="X-txtb">
          <div{i('X-httl')}><div class="X-kick" style="font-size:22px">MARKETING OLFACTIF AU MALI</div><div class="X-ttl">Éveillez vos <em>sens</em></div></div>
          <div class="X-p"{i('X-htxt')}>Diffuseurs et fragrances pour hôtels, bureaux, maison et voiture.</div>
          <div class="X-btns"{i('X-hbtn')}><div class="X-btn">DÉCOUVRIR NOS SOLUTIONS</div><div class="X-btn ol">CONTACTER UN CONSEILLER</div></div>
        </div>'''

F = {}
# ── 01 · 0–5 s · logo, golden curve, the curve becomes the screen ─────────
RR = 'M 540 200 H 892 Q 940 200 940 248 V 1282 Q 940 1330 892 1330 H 188 Q 140 1330 140 1282 V 248 Q 140 200 188 200 Z'
F['01-signature'] = ('''
    #X-logo { position: absolute; left: 160px; top: 614px; width: 760px; height: 411px; }
    #X-logo img { display: block; width: 100%; }
    #X-scr { position: absolute; left: 140px; top: 200px; width: 800px; height: 1130px; border-radius: 48px; overflow: hidden; }
''', '''    <div class="X-full" style="background:#000"></div>
    <canvas class="X-cv" id="X-mist" width="1080" height="1920"></canvas>
    <svg class="X-a" style="left:0;top:0" width="1080" height="1920" viewBox="0 0 1080 1920">
      <path id="X-cur" d="M 150 1180 C 230 880 470 690 760 740 C 960 780 1000 1010 850 1060 C 720 1100 650 970 740 915 C 800 880 860 930 830 985" stroke="#E9C221" stroke-width="5" fill="none" stroke-linecap="round"/>
      <path id="X-rr" d="''' + RR + '''" stroke="#E9C221" stroke-width="4" fill="none"/>
    </svg>
    <div id="X-scr"><div class="X-home" id="X-home">''' + home() + '''</div></div>
    <div id="X-logo"><img src="assets/images/sensexpress-logo.png" alt="SensExpress"></div>
''' + statement('Une signature', 'qui se voit.', 1440, 'SENSEXPRESS / DESIGN DU SITE'), drive('SX.mist(R("#X-mist"), { x: 540, y: 1500, spread: 260, rise: 1100, size: 90, alpha: 0.07, n: 40, seed: 3 })', 5.6) + '''
      const cur = R("#X-cur"), CL = cur.getTotalLength(), rr = R("#X-rr"), RL = rr.getTotalLength();
      tl.fromTo(R("#X-logo"), { opacity: 0, scale: 0.94, filter: "blur(10px)" }, { opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.8, ease: "power2.out" }, 0.15);
      tl.fromTo(cur, { attr: { "stroke-dasharray": CL, "stroke-dashoffset": CL } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.5, ease: "power2.inOut" }, 0.85);
      tl.to(cur, { opacity: 0, duration: 0.6, ease: "power2.in" }, 2.55);
      tl.fromTo(rr, { attr: { "stroke-dasharray": RL, "stroke-dashoffset": RL } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.0, ease: "power2.inOut" }, 2.4);
      // the logo settles into the header of the page
      tl.to(R("#X-logo"), { x: -300, y: -563, scale: 0.17, duration: 0.85, ease: "power3.inOut" }, 2.55);
      tl.to(R("#X-logo"), { opacity: 0, duration: 0.15 }, 3.4);
      tl.fromTo(R("#X-scr"), { clipPath: "circle(0% at 50% 0%)" }, { clipPath: "circle(150% at 50% 0%)", duration: 1.1, ease: "power2.inOut" }, 2.85);
      tl.to(rr, { opacity: 0.35, duration: 0.6 }, 3.6);
''' + st_in(3.75, kick=True))

# ── 02 · 5–12 s · the page splits into layers, the palette, then rebuilds ──
LAB = [('Image', 'ambiance du site', 712), ('Titre', 'Playfair Display', 935), ('Texte', 'Montserrat', 1035), ('Bouton', 'or #E9C221', 1150)]
lab_html = ''.join(f'''    <div class="X-a X-lab" id="X-lb{i}" style="left:760px; top:{y - 34}px"><i></i><div><b>{a}</b><span>{b}</span></div></div>\n''' for i, (a, b, y) in enumerate(LAB))
COLS = [('#E9C221', 'Or', '#000'), ('#000000', 'Noir', '#fff'), ('#121212', 'Gris sombre', '#fff'), ('#FFFFFF', 'Blanc', '#000')]
col_html = ''.join(f'''    <div class="X-a X-col" id="X-c{i}" style="left:{i * 270}px; background:{c}; color:{fg}"><div><b>{n}</b><span>{c}</span></div></div>\n''' for i, (c, n, fg) in enumerate(COLS))
F['02-sens'] = ('''
    #X-stage { position: absolute; left: 140px; top: 200px; width: 800px; height: 1130px; perspective: 2400px; transform-origin: 0 0; }
    #X-stk { position: absolute; inset: 0; transform-style: preserve-3d; }
    .X-ly { position: absolute; left: 0; width: 800px; }
    #X-L0 { top: 0; height: 612px; background: #000; overflow: hidden; }
    #X-L1 { top: 612px; padding: 52px 48px 0; }
    #X-L2 { top: 810px; padding: 0 48px; }
    #X-L3 { top: 960px; padding: 0 48px; }
    #X-base { position: absolute; inset: 0; background: #000; border-radius: 48px; border: 2px solid rgba(233,194,33,0.35); }
    .X-lab { display: flex; align-items: center; gap: 14px; }
    .X-lab i { display: block; width: 44px; height: 2px; background: #E9C221; }
    .X-lab b { display: block; font-family: "Playfair Display"; font-weight: 600; font-size: 38px; color: #FFFFFF; }
    .X-lab span { display: block; font-family: "Montserrat"; font-weight: 400; font-size: 22px; color: #BDBDBD; white-space: nowrap; }
    .X-col { top: 0; width: 270px; height: 1920px; display: flex; align-items: flex-end; justify-content: center; padding-bottom: 330px; border-right: 1px solid rgba(255,255,255,0.08); }
    .X-col b { display: block; font-family: "Playfair Display"; font-weight: 600; font-size: 40px; text-align: center; }
    .X-col span { display: block; margin-top: 8px; font-family: "Montserrat"; font-weight: 500; font-size: 24px; letter-spacing: 0.08em; text-align: center; opacity: 0.85; }
    #X-flat { background: #E9C221; }
''', '''    <div class="X-full" style="background:linear-gradient(180deg,#000 0%,#0b0b0b 60%,#121212 100%)"></div>
''' + statement('Le design', 'éveille les sens.', 200) + '''    <div id="X-stage"><div id="X-base"></div><div id="X-stk">
      <div class="X-ly" id="X-L0"><div class="X-hd"><img src="assets/images/sensexpress-logo.png" alt="SensExpress"><div class="X-bg"><i></i><i></i><i></i></div></div><div class="X-img">''' + HERO_SVG + '''</div></div>
      <div class="X-ly" id="X-L1"><div class="X-kick" style="font-size:22px">MARKETING OLFACTIF AU MALI</div><div class="X-ttl">Éveillez vos <em>sens</em></div></div>
      <div class="X-ly" id="X-L2"><div class="X-p" style="margin:0">Diffuseurs et fragrances pour hôtels, bureaux, maison et voiture.</div></div>
      <div class="X-ly" id="X-L3"><div class="X-btns" style="margin:0"><div class="X-btn">DÉCOUVRIR NOS SOLUTIONS</div><div class="X-btn ol">CONTACTER UN CONSEILLER</div></div></div>
    </div></div>
''' + lab_html + '''    <div class="X-full" id="X-flat"></div>
''' + col_html, st_in(0.25) + '''      // match cut from 01: the page arrives full size, then steps back to make room
      tl.fromTo(R("#X-stage"), { x: 0, y: 0, scale: 1 }, { x: -60, y: 270, scale: 0.72, duration: 0.9, ease: "power3.inOut" }, 0.1);
      tl.to(R("#X-base"), { opacity: 0, duration: 0.5 }, 0.9);
      tl.fromTo(R("#X-stk"), { rotationY: 0, rotationX: 0 }, { rotationY: -24, rotationX: 10, duration: 1.1, ease: "power2.inOut" }, 1.0);
      [0, 1, 2, 3].forEach((i) => tl.fromTo(R("#X-L" + i), { z: 0, x: 0 }, { z: 150 - i * 90, x: i * 36, duration: 1.1, ease: "power2.inOut", immediateRender: false }, 1.0));
      [0, 1, 2, 3].forEach((i) => tl.fromTo(R("#X-lb" + i), { opacity: 0, x: 30 }, { opacity: 1, x: 0, duration: 0.5, ease: "power2.out" }, 1.7 + i * 0.22));
      tl.to(RA(".X-lab"), { opacity: 0, duration: 0.4, ease: "power2.in" }, 3.35);
      // a flat of gold links to the palette, which opens into four columns
      tl.fromTo(R("#X-flat"), { clipPath: "inset(100% 0% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.6, ease: "power3.inOut" }, 3.55);
      [0, 1, 2, 3].forEach((i) => tl.fromTo(R("#X-c" + i), { y: 1920 }, { y: 0, duration: 0.55, ease: "power3.out" }, 4.1 + i * 0.1));
      tl.set(R("#X-flat"), { opacity: 0 }, 4.7);
      tl.to(R("#X-stk"), { rotationY: 0, rotationX: 0, duration: 0.01 }, 4.7);
      [0, 1, 2, 3].forEach((i) => tl.set(R("#X-L" + i), { z: 0, x: 0 }, 4.7));
      [0, 1, 2, 3].forEach((i) => tl.to(R("#X-c" + i), { y: -1920, duration: 0.6, ease: "power3.in" }, 5.45 + i * 0.09));
      tl.fromTo(R("#X-base"), { opacity: 0 }, { opacity: 1, duration: 0.5 }, 5.6);
''')

# ── 03 · 12–20 s · four categories in arched windows, then one page ──────
ICONS = [
 '<path d="M 70 330 H 430 M 50 352 H 450 M 100 320 A 150 150 0 0 1 400 320 M 236 168 H 264 M 250 168 V 146 M 170 250 A 100 100 0 0 1 220 200"/>',
 '<path d="M 70 170 L 250 80 L 430 170 Z M 85 192 H 415 M 120 210 V 330 M 200 210 V 330 M 300 210 V 330 M 380 210 V 330 M 75 345 H 425 M 55 368 H 445"/>',
 '<path d="M 80 220 L 250 90 L 420 220 M 115 195 V 370 H 385 V 195 M 220 370 V 290 H 280 V 370 M 145 250 H 195 V 300 H 145 Z M 305 250 H 355 V 300 H 305 Z"/>',
 '<path d="M 50 320 H 85 A 40 40 0 0 1 165 320 H 335 A 40 40 0 0 1 415 320 H 455 V 280 Q 452 258 420 252 L 360 242 L 300 190 Q 286 178 262 178 H 160 Q 140 178 126 192 L 88 238 Q 52 246 50 270 Z M 125 320 m -28 0 a 28 28 0 1 0 56 0 a 28 28 0 1 0 -56 0 M 375 320 m -28 0 a 28 28 0 1 0 56 0 a 28 28 0 1 0 -56 0 M 120 242 L 160 200 H 228 V 242 Z M 248 242 V 200 H 285 L 330 242 Z"/>',
]
CATS = [('Hôtel, Lobby,<br>Réception', 'radial-gradient(80% 60% at 50% 32%, #4d3812 0%, #150f06 60%, #070605 100%)'),
        ('Banque, Bureau,<br>Entreprise', 'radial-gradient(80% 60% at 50% 32%, #2a2d33 0%, #0e0f11 60%, #050506 100%)'),
        ('Home', 'radial-gradient(80% 60% at 50% 32%, #3b2a1a 0%, #120c08 60%, #060504 100%)'),
        ('Voitures', 'radial-gradient(80% 60% at 50% 32%, #262626 0%, #0c0c0c 60%, #030303 100%)')]
arch_html = ''.join(f'''    <div class="X-arch" id="X-w{i}"><div class="X-in" id="X-wi{i}" style="background:{bg}">
      <canvas id="X-wm{i}" width="720" height="1120" style="position:absolute;left:0;top:0"></canvas>
      <svg class="ic" viewBox="0 0 500 500"><g id="X-ic{i}" stroke="#E9C221" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round">{ICONS[i]}</g></svg>
      <div class="X-al" id="X-wl{i}"><span>0{i + 1} / 04</span><b>{n}</b></div>
    </div></div>
''' for i, (n, bg) in enumerate(CATS))
GRID = [(360, 760), (720, 760), (360, 1300), (720, 1300)]
F['03-univers'] = ('', '''    <div class="X-full" style="background:radial-gradient(90% 60% at 50% 55%, #1a1a1a 0%, #121212 50%, #000 100%)"></div>
''' + statement('Des univers', 'à explorer.', 200) + arch_html, st_in(0.2) + '''      const AT = [0.45, 2.15, 3.85, 5.55], GRID = ''' + json.dumps(GRID) + ''';
      const M = [0, 1, 2, 3].map((i) => SX.mist(R("#X-wm" + i), { x: 360, y: 760, spread: 140, rise: 620, size: 70, alpha: 0.1, n: 30, seed: 11 + i }));
      const ms = { t: 0 };
      tl.fromTo(ms, { t: 0 }, { t: 8.6, duration: 8.6, ease: "none", onUpdate: () => M.forEach((m, i) => m(ms.t, ms.t > AT[i] ? 1 : 0)) }, 0);
      M.forEach((m) => m(0, 0));
      [0, 1, 2, 3].forEach((i) => {
        const t0 = AT[i], g = R("#X-ic" + i);
        tl.fromTo(R("#X-w" + i), { clipPath: "inset(100% 0% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.8, ease: "power3.inOut" }, t0);
        tl.fromTo(R("#X-wi" + i), { scale: 1.14 }, { scale: 1, duration: 1.7, ease: "power2.out" }, t0);
        g.querySelectorAll("path").forEach((p) => { const L = p.getTotalLength(); tl.fromTo(p, { attr: { "stroke-dasharray": L, "stroke-dashoffset": L } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.1, ease: "power2.inOut" }, t0 + 0.3); });
        tl.fromTo(R("#X-wl" + i), { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, t0 + 0.55);
      });
      // the four windows gather into one page
      [0, 1, 2, 3].forEach((i) => tl.to(R("#X-w" + i), { x: GRID[i][0] - 540, y: GRID[i][1] - 1030, scale: 0.46, duration: 0.9, ease: "power3.inOut" }, 7.2 + i * 0.05));
''')

# ── 04 · 20–28 s · a component opens « Nos Services », a diffuser in light ──
F['04-solutions'] = ('''
    #X-sec { position: absolute; left: 0; right: 0; top: 440px; text-align: center; }
    #X-sec .X-kick { font-size: 24px; }
    #X-sec b { display: block; margin-top: 14px; font-family: "Playfair Display"; font-weight: 600; font-size: 64px; color: #FFFFFF; }
    #X-sec b em { font-style: normal; color: #E9C221; }
    #X-lbl { position: absolute; left: 0; right: 0; top: 1335px; text-align: center; }
    #X-lbl b { display: block; font-family: "Playfair Display"; font-weight: 600; font-size: 44px; color: #FFFFFF; }
    #X-lbl span { display: block; margin-top: 8px; font-family: "Montserrat"; font-weight: 400; font-size: 26px; color: #BDBDBD; }
    #X-cta { position: absolute; left: 290px; top: 1468px; width: 500px; }
''', '''    <div class="X-full" style="background:radial-gradient(80% 50% at 50% 55%, #241c0a 0%, #121212 45%, #000 100%)" id="X-bgp"></div>
    <canvas class="X-cv" id="X-3d" width="1080" height="1920"></canvas>
''' + statement('Des solutions', 'à découvrir.', 200) + '''    <div id="X-sec"><div class="X-kick">NOS SERVICES</div><b>Diffuseurs <em>&amp;</em> fragrances</b></div>
    <div id="X-lbl"><b>Diffuseur de parfum</b><span>Hôtels, bureaux, maison et voiture</span></div>
    <div id="X-cta"><div class="X-btn" id="X-cb">DÉCOUVRIR</div></div>
    <svg class="X-a" style="left:0;top:0" width="1080" height="1920" viewBox="0 0 1080 1920"><rect id="X-frame" x="194" y="502" width="331" height="515" rx="24" stroke="#E9C221" stroke-width="3" fill="none"/></svg>
''', drive('SX.diffuser(R("#X-3d"), { mist: 1.2, push: [1.0, 3.6], pull: [4.7, 1.4], pullDist: 13.5, pullLook: 0.8 })', 8.6) + '''      // the component frame grows to open the page
      tl.fromTo(R("#X-frame"), { attr: { x: 194, y: 502, width: 331, height: 515 }, opacity: 1 }, { attr: { x: 40, y: 40, width: 1000, height: 1840 }, duration: 0.9, ease: "power3.inOut" }, 0);
      tl.to(R("#X-frame"), { opacity: 0, duration: 0.6 }, 1.0);
      tl.fromTo(R("#X-bgp"), { opacity: 0 }, { opacity: 1, duration: 0.7 }, 0.3);
      tl.fromTo(R("#X-3d"), { opacity: 0 }, { opacity: 1, duration: 0.9, ease: "power2.out" }, 0.7);
''' + st_in(0.9) + '''      // back to the section title and its button
      tl.fromTo(R("#X-sec"), { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.7, ease: "power2.out" }, 5.0);
      tl.fromTo(R("#X-lbl"), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, 5.4);
      tl.fromTo(R("#X-cta"), { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, 5.7);
      tl.fromTo(R("#X-cb"), { boxShadow: "0 0 0 0 rgba(233,194,33,0)" }, { boxShadow: "0 0 0 14px rgba(233,194,33,0.18)", duration: 0.6, ease: "power2.out", yoyo: true, repeat: 1 }, 6.8);
''')

# ── 05 · 28–36 s · the line leads to the contact button, then computer and phone ──
DESK = '''<div style="position:absolute;inset:0;background:#000">
          <div style="height:62px;display:flex;align-items:center;gap:26px;padding:0 30px;border-bottom:1px solid #1d1d1d"><img src="assets/images/sensexpress-logo.png" alt="" style="height:40px"><div style="margin-left:auto;display:flex;gap:26px;font-family:Montserrat;font-weight:500;font-size:13px;letter-spacing:.14em;color:#fff"><span>ACCUEIL</span><span>NOS SERVICES</span><span>CONTACT</span></div><div style="padding:9px 14px;background:#E9C221;color:#000;font-family:Montserrat;font-weight:600;font-size:12px;letter-spacing:.12em">CONTACTER UN CONSEILLER</div></div>
          <div style="display:flex;height:438px">
            <div style="flex:1;padding:70px 0 0 44px"><div class="X-kick" style="font-size:13px">MARKETING OLFACTIF AU MALI</div><div style="margin-top:12px;font-family:'Playfair Display';font-weight:600;font-size:50px;line-height:1.08;color:#fff">Éveillez vos <span style="color:#E9C221">sens</span></div><div style="margin-top:14px;font-family:Montserrat;font-size:16px;line-height:1.55;color:#c9c9c9">Diffuseurs et fragrances pour hôtels,<br>bureaux, maison et voiture.</div><div style="margin-top:24px;display:inline-block;padding:13px 20px;background:#E9C221;color:#000;font-family:Montserrat;font-weight:600;font-size:12px;letter-spacing:.14em">DÉCOUVRIR NOS SOLUTIONS</div></div>
            <div style="position:relative;width:420px;overflow:hidden;background:radial-gradient(70% 70% at 55% 40%,#4a3712 0%,#1a1308 50%,#070605 100%)"><div style="position:absolute;left:-190px;top:-30px;transform:scale(0.9);transform-origin:0 0">''' + HERO_SVG + '''</div></div>
          </div></div>'''
F['05-echange'] = ('''
    #X-card { position: absolute; left: 120px; top: 560px; width: 840px; height: 560px; background: #121212; border: 1px solid #262626; padding: 64px 60px 0; }
    #X-card b { display: block; margin-top: 16px; font-family: "Playfair Display"; font-weight: 600; font-size: 58px; color: #FFFFFF; }
    #X-card p { margin-top: 18px; font-family: "Montserrat"; font-weight: 400; font-size: 28px; line-height: 1.5; color: #C9C9C9; }
    #X-cbtn { position: absolute; left: 60px; right: 60px; bottom: 64px; }
    #X-rip { position: absolute; left: 540px; top: 1017px; width: 20px; height: 20px; margin: -10px 0 0 -10px; border-radius: 50%; border: 3px solid #E9C221; opacity: 0; }
    #X-mon { position: absolute; left: 90px; top: 520px; width: 900px; }
    #X-mon .scr { position: relative; width: 900px; height: 530px; border: 14px solid #1b1b1b; border-radius: 18px; overflow: hidden; background: #000; box-shadow: 0 40px 90px rgba(0,0,0,0.6); }
    #X-mon .neck { width: 120px; height: 90px; margin: 0 auto; background: linear-gradient(#202020, #121212); }
    #X-mon .foot { width: 320px; height: 16px; margin: 0 auto; border-radius: 8px; background: #1e1e1e; }
    #X-ph { position: absolute; left: 600px; top: 850px; width: 370px; height: 740px; border-radius: 52px; border: 12px solid #1b1b1b; background: #000; overflow: hidden; box-shadow: 0 40px 90px rgba(0,0,0,0.7); }
    #X-ph .X-home { transform: scale(0.445); transform-origin: 0 0; }
''', '''    <div class="X-full" style="background:linear-gradient(180deg,#000 0%,#0d0d0d 100%)"></div>
''' + statement('Un projet commence', 'par un échange.', 200) + '''    <div id="X-card"><div class="X-kick">CONTACT</div><b>Parlons de votre projet</b><p>Un conseiller vous accompagne dans le choix de vos diffuseurs et de vos fragrances.</p>
      <div id="X-cbtn"><div class="X-btn" id="X-cb">CONTACTER UN CONSEILLER</div></div></div>
    <svg class="X-a" style="left:0;top:0" width="1080" height="1920" viewBox="0 0 1080 1920"><path id="X-ln" d="M 60 470 C 620 410 1050 520 1012 760 C 985 960 960 1017 905 1017" stroke="#E9C221" stroke-width="5" fill="none" stroke-linecap="round"/></svg>
    <div id="X-rip"></div>
    <div id="X-mon"><div class="scr">''' + DESK + '''</div><div class="neck"></div><div class="foot"></div></div>
    <div id="X-ph"><div class="X-home">''' + home(False) + '''</div></div>
''', st_in(0.2) + '''      const ln = R("#X-ln"), LL = ln.getTotalLength();
      tl.fromTo(R("#X-card"), { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.7, ease: "power2.out" }, 0.35);
      tl.fromTo(ln, { attr: { "stroke-dasharray": LL, "stroke-dashoffset": LL } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.5, ease: "power2.inOut" }, 0.8);
      tl.fromTo(R("#X-cb"), { boxShadow: "0 0 0 0 rgba(233,194,33,0)" }, { boxShadow: "0 0 0 12px rgba(233,194,33,0.22)", duration: 0.4, ease: "power2.out" }, 2.25);
      tl.fromTo(R("#X-rip"), { opacity: 1, scale: 0.4 }, { opacity: 0, scale: 9, duration: 0.8, ease: "power2.out" }, 2.4);
      tl.to([R("#X-card"), ln], { opacity: 0, y: -30, duration: 0.6, ease: "power2.in" }, 3.2);
      tl.fromTo(R("#X-mon"), { opacity: 0, y: 60, scale: 0.96 }, { opacity: 1, y: 0, scale: 1, duration: 0.8, ease: "power3.out" }, 3.6);
      tl.to(R("#X-mon"), { x: -30, y: -40, scale: 0.92, duration: 0.8, ease: "power3.inOut" }, 5.3);
      tl.fromTo(R("#X-ph"), { opacity: 0, y: 140 }, { opacity: 1, y: 0, duration: 0.8, ease: "power3.out" }, 5.4);
''')

# ── 06 · 36–42 s · logo on black, then the address alone from 38 s ────────
F['06-adresse'] = ('''
    #X-logo { position: absolute; left: 160px; top: 654px; width: 760px; height: 411px; }
    #X-logo img { display: block; width: 100%; }
    #X-url { position: absolute; left: 0; right: 0; top: 880px; text-align: center; font-family: "Playfair Display"; font-weight: 600; font-size: 104px; color: #FFFFFF; }
    #X-url em { font-style: normal; color: #E9C221; }
''', '''    <div class="X-full" style="background:#000"></div>
    <svg class="X-a" style="left:0;top:0" width="1080" height="1920" viewBox="0 0 1080 1920">
      <path id="X-cur" d="M 150 1220 C 230 920 470 730 760 780 C 960 820 1000 1050 850 1100" stroke="#E9C221" stroke-width="4" fill="none" stroke-linecap="round" opacity="0.7"/>
      <path id="X-ul" d="M 380 1050 C 470 1030 610 1030 700 1050" stroke="#E9C221" stroke-width="4" fill="none" stroke-linecap="round"/>
    </svg>
    <div id="X-logo"><img src="assets/images/sensexpress-logo.png" alt="SensExpress"></div>
    <div id="X-url">sensexpress<em>.com</em></div>
''', '''      const cur = R("#X-cur"), CL = cur.getTotalLength(), ul = R("#X-ul"), UL = ul.getTotalLength();
      tl.fromTo(R("#X-logo"), { opacity: 0, scale: 0.95 }, { opacity: 1, scale: 1, duration: 0.8, ease: "power2.out" }, 0.1);
      tl.fromTo(cur, { attr: { "stroke-dasharray": CL, "stroke-dashoffset": CL } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.2, ease: "power2.inOut" }, 0.2);
      tl.to([R("#X-logo"), cur], { opacity: 0, duration: 0.5, ease: "power2.in" }, 1.45);
      tl.fromTo(R("#X-url"), { opacity: 0, y: 26 }, { opacity: 1, y: 0, duration: 0.8, ease: "power3.out" }, 2.0);
      tl.fromTo(ul, { attr: { "stroke-dasharray": UL, "stroke-dashoffset": UL } }, { attr: { "stroke-dashoffset": 0 }, duration: 0.9, ease: "power2.inOut" }, 2.4);
''')

def frame(fid, dur, css, html, js):
    pre = 's' + fid[:2]
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
br = ''.join(f'      <audio id="el-breath{i}" src="assets/breath.wav" data-start="{t}" data-duration="1.1" data-track-index="{12 + i}" data-volume="0.35"></audio>\n' for i, t in enumerate([4.55, 19.55, 35.55]))
idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/three.min.js"></script>
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
