# SensExpress — « Les Diffuseurs » : film de marque 37 s, vertical 1080×1920, 25 i/s.
# Direction : luxe sensoriel (Apple / Aesop / Diptyque). Fond noir #08080C toujours vivant (halos dorés, poussière,
# reflet lent — assets/vendor/aura.js), brume physique qui ondule et se dissipe, typo à flou cinétique,
# formes qui se transforment d'une scène à l'autre. Photos produits : site sensexpress.com (captures client),
# agrandies ×4 par super-résolution EDSR. Textes produits repris du site, sans prix (non lisibles pour 3 modèles).
import os, json
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, TOTAL, OV = 1080, 1920, 37.0, 0.6
TOK = {'%BG%': '#08080C', '%GOLD%': '#D4AF37', '%CHAMP%': '#F5E6D3', '%MUTE%': '#B9AE9E'}
SC = [('01-respirez', 0.0, 5.0), ('02-manifeste', 5.0, 4.2), ('03-prince', 9.2, 5.4), ('04-duchesse', 14.6, 5.2),
      ('05-monarque', 19.8, 5.2), ('06-trio', 25.0, 5.6), ('07-signature', 30.6, 2.8), ('08-logo', 33.4, 3.6)]
# product photos: (file, width, height, nozzle fraction x, y, jet direction in radians from vertical)
IMG = {'prince': (0.500, 0.215, 0.0), 'duchesse': None, 'senspro': (0.775, 0.262, 0.15), 'monarque': (0.511, 0.200, 0.0),
       'nomade': (0.686, 0.313, 0.35), 'duosens': (0.627, 0.352, 0.0)}
SIZES = json.load(open(f'{P}/assets/images/sizes.json'))

FONTS = '''
    @font-face { font-family: "Cormorant"; font-weight: 300; src: url("assets/fonts/cormorant-garamond-latin-300-normal.woff2") format("woff2"); }
    @font-face { font-family: "Cormorant"; font-weight: 300; font-style: italic; src: url("assets/fonts/cormorant-garamond-latin-300-italic.woff2") format("woff2"); }
    @font-face { font-family: "Cormorant"; font-weight: 400; font-style: italic; src: url("assets/fonts/cormorant-garamond-latin-400-italic.woff2") format("woff2"); }
    @font-face { font-family: "Cormorant"; font-weight: 500; src: url("assets/fonts/cormorant-garamond-latin-500-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 400; src: url("assets/fonts/montserrat-latin-400-normal.woff2") format("woff2"); }
    @font-face { font-family: "Montserrat"; font-weight: 500; src: url("assets/fonts/montserrat-latin-500-normal.woff2") format("woff2"); }
'''
CSS = '''
    .X-a { position: absolute; }
    .X-c { left: 0; right: 0; text-align: center; }
    .X-cv { position: absolute; left: 0; top: 0; }
    .X-d { font-family: "Cormorant"; font-weight: 300; color: %CHAMP%; white-space: nowrap; line-height: 1.05; }
    .X-i { font-family: "Cormorant"; font-weight: 300; font-style: italic; color: %CHAMP%; white-space: nowrap; line-height: 1.05; }
    .X-cap { font-family: "Montserrat"; font-weight: 500; font-size: 25px; letter-spacing: 0.34em; color: %GOLD%; white-space: nowrap; text-transform: uppercase; }
    .X-w { display: inline-block; }
    .X-frame { position: absolute; overflow: hidden; background: #000; -webkit-mask-image: linear-gradient(180deg, #000 0%, #000 72%, rgba(0,0,0,0) 100%); mask-image: linear-gradient(180deg, #000 0%, #000 72%, rgba(0,0,0,0) 100%); }
    .X-frame img { position: absolute; left: 0; top: 0; width: 100%; height: 100%; object-fit: cover; display: block; }
    .X-frame canvas { position: absolute; left: 0; top: 0; }
    .X-line { position: absolute; height: 1px; background: linear-gradient(90deg, rgba(212,175,55,0), %GOLD%, rgba(212,175,55,0)); }
    .X-glow { position: absolute; border-radius: 50%; background: radial-gradient(closest-side, rgba(212,175,55,0.38), rgba(212,175,55,0.08) 55%, rgba(212,175,55,0)); }
'''
EXPO = 'expo.out'
def words(text, cls, style, wid, extra=''):
    ws = ''.join(f'<span class="X-w">{w}</span>' + (' ' if k < len(text.split(' ')) - 1 else '') for k, w in enumerate(text.split(' ')))
    return f'    <div class="X-a X-c {cls}" id="{wid}" style="{style}" {extra}>{ws}</div>\n'
def blur_in(sel, at, d=1.4, y=34, b=16, stagger=0.11, all_=True):
    q = f'RA("{sel} .X-w")' if all_ else f'R("{sel}")'
    return f'      tl.fromTo({q}, {{ opacity: 0, y: {y}, filter: "blur({b}px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: {d}, ease: "{EXPO}", stagger: {stagger} }}, {at});\n'
def blur_out(sels, at, d=0.9, y=-26, b=14):
    q = '[' + ', '.join(f'R("{s}")' for s in sels) + ']'
    return f'      tl.to({q}, {{ opacity: 0, y: {y}, filter: "blur({b}px)", duration: {d}, ease: "power2.in", stagger: 0.04 }}, {at});\n'
def fade_in(sel, at, d=1.2, y=14):
    return f'      tl.fromTo(R("{sel}"), {{ opacity: 0, y: {y} }}, {{ opacity: 1, y: 0, duration: {d}, ease: "power3.out" }}, {at});\n'
def line_in(sel, at, d=1.2):
    return f'      tl.fromTo(R("{sel}"), {{ scaleX: 0, opacity: 0 }}, {{ scaleX: 1, opacity: 1, duration: {d}, ease: "{EXPO}" }}, {at});\n'

ARCH = (380, 380, 40, 40)
def frame(fid, img, x, y, w, h, radius=ARCH, vap=None, seed=11):
    """Photo window with optional vapour canvas aligned on the product's nozzle (object-fit: cover maths)."""
    iw, ih = SIZES[img]; s = max(w / iw, h / ih); ox, oy = (w - iw * s) / 2, (h - ih * s) / 2
    r = ' '.join(f'{v}px' for v in radius)
    html = f'    <div class="X-frame" id="{fid}" style="left:{x}px; top:{y}px; width:{w}px; height:{h}px; border-radius:{r}"><img id="{fid}i" src="assets/images/{img}.jpg" alt="">'
    js = ''
    noz = IMG.get(img)
    if noz and vap is not False:
        nx, ny, dr = noz[0] * iw * s + ox, noz[1] * ih * s + oy, noz[2]
        html += f'<canvas id="{fid}v" width="{w}" height="{h}"></canvas>'
        o = {'x': round(nx, 1), 'y': round(ny, 1), 'dir': dr, 'rise': round(ny * 0.95), 'size': 70, 'alpha': 0.2, 'n': 60, 'life': 3.4, 'seed': seed}
        if vap: o.update(vap)
        js = f'AURA.vapour(R("#{fid}v"), {json.dumps(o)})'
    html += '</div>\n'
    return html, js, f'inset(0% 0% 0% 0% round {r})', f'inset(40% 34% 40% 34% round {w}px {w}px {w}px {w}px)'
def morph_in(fid, closed, open_, at, d=1.8):
    return (f'      tl.fromTo(R("#{fid}"), {{ clipPath: "{closed}", opacity: 0 }}, {{ clipPath: "{open_}", opacity: 1, duration: {d}, ease: "{EXPO}" }}, {at});\n'
            f'      tl.fromTo(R("#{fid}i"), {{ scale: 1.18, filter: "blur(10px) brightness(0.7)" }}, {{ scale: 1.0, filter: "blur(0px) brightness(1)", duration: {d + 2.6}, ease: "power2.out" }}, {at});\n')
def morph_out(fid, closed, at, d=1.0):
    return f'      tl.to(R("#{fid}"), {{ clipPath: "{closed}", opacity: 0, filter: "blur(8px)", duration: {d}, ease: "power3.in" }}, {at});\n'
def drive(dur, makers):
    """One proxy tween feeds every canvas renderer with scene-local time (seek-safe)."""
    if not makers: return ''
    lines = ''.join(f'      const __r{i} = {m};\n' for i, m in enumerate(makers))
    calls = '; '.join(f'__r{i}(__p.t)' for i in range(len(makers)))
    return lines + f'''      const __p = {{ t: 0 }};
      tl.fromTo(__p, {{ t: 0 }}, {{ t: {dur}, duration: {dur}, ease: "none", onUpdate: () => {{ {calls}; }} }}, 0);
      {calls};
'''

F = {}
# ── 01 · Respirez ───────────────────────────────────────────────────────────
F['01-respirez'] = ('''
    #X-orb { left: 140px; top: 460px; width: 800px; height: 800px; }
''', '''    <canvas class="X-cv" id="X-v" width="1080" height="1920"></canvas>
    <div class="X-glow" id="X-orb"></div>
    <div class="X-a X-c X-i" id="X-t" style="top:770px; font-size:200px">Respirez.</div>
    <div class="X-a X-c X-cap" id="X-k" style="top:1060px; letter-spacing:0.55em">SensExpress</div>
''', drive(5.6, ['AURA.vapour(R("#X-v"), { x: 540, y: 2050, rise: 1500, size: 300, alpha: 0.12, n: 55, life: 6.5, seed: 4 })']) +
 '      tl.fromTo(R("#X-orb"), { scale: 0.1, opacity: 0 }, { scale: 1, opacity: 1, duration: 3.0, ease: "power2.out" }, 0.2);\n'
 '      tl.fromTo(R("#X-t"), { opacity: 0, scale: 1.1, filter: "blur(34px)" }, { opacity: 1, scale: 1, filter: "blur(0px)", duration: 2.4, ease: "expo.out" }, 0.9);\n' +
 fade_in('#X-k', 2.0, 1.4, 0) +
 '      tl.to(R("#X-t"), { opacity: 0, y: -90, scale: 1.06, filter: "blur(26px)", duration: 1.5, ease: "power2.in" }, 3.9);\n'
 '      tl.to([R("#X-k"), R("#X-orb")], { opacity: 0, duration: 1.2, ease: "power2.in" }, 4.1);\n')

# ── 02 · manifeste ─────────────────────────────────────────────────────────
F['02-manifeste'] = ('', words('Un parfum peut', 'X-d', 'top:690px; font-size:118px', 'X-l1') +
 words("changer l'âme", 'X-i', 'top:830px; font-size:150px; color:%GOLD%', 'X-l2') +
 words("d'un lieu.", 'X-d', 'top:1000px; font-size:118px', 'X-l3') +
 '    <div class="X-line" id="X-ln" style="left:390px; top:1190px; width:300px"></div>\n',
 blur_in('#X-l1', 0.35) + blur_in('#X-l2', 0.9, 1.6) + blur_in('#X-l3', 1.5) + line_in('#X-ln', 2.0, 1.4) +
 blur_out(['#X-l1', '#X-l2', '#X-l3', '#X-ln'], 3.6, 0.9))

# ── 03 · Le Prince ─────────────────────────────────────────────────────────
fh, fj, fo, fc = frame('X-f', 'prince', 160, 200, 760, 1000, vap={'alpha': 0.24}, seed=21)
F['03-prince'] = ('', fh + '''    <div class="X-a X-c X-i" id="X-n" style="top:1225px; font-size:150px">Le Prince</div>
    <div class="X-a X-c X-cap" id="X-s1" style="top:1430px">Tactile · via application</div>
    <div class="X-a X-c X-d" id="X-s2" style="top:1490px; font-size:66px">Jusqu'à 300 m²</div>
''', drive(6.0, [fj]) + morph_in('X-f', fc, fo, 0.1) +
 '      tl.fromTo(R("#X-n"), { opacity: 0, y: 40, filter: "blur(18px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 1.6, ease: "expo.out" }, 0.9);\n' +
 fade_in('#X-s1', 1.5) + fade_in('#X-s2', 1.8) + morph_out('X-f', fc, 4.55) + blur_out(['#X-n', '#X-s1', '#X-s2'], 4.5, 0.8))

# ── 04 · La Duchesse ───────────────────────────────────────────────────────
fh, fj, fo, fc = frame('X-f', 'duchesse', 230, 190, 620, 900, radius=(44, 44, 44, 44))
F['04-duchesse'] = ('''
    #X-f img { filter: brightness(0.82) contrast(1.06); }
''', fh + '''    <div class="X-a X-c X-i" id="X-n" style="top:1120px; font-size:130px">La Duchesse</div>
    <div class="X-a X-c" id="X-num" style="top:1270px"><span class="X-d" style="font-size:190px; color:%GOLD%" id="X-v">0</span><span class="X-d" style="font-size:90px; color:%GOLD%; margin-left:18px">m²</span></div>
    <div class="X-a X-c X-cap" id="X-s1" style="top:1260px">Jusqu'à</div>
    <div class="X-a X-c X-cap" id="X-s2" style="top:1500px; color:%CHAMP%; letter-spacing:0.26em">Hôtels · aéroports · showrooms</div>
''', morph_in('X-f', fc, fo, 0.1) +
 '      tl.fromTo(R("#X-n"), { opacity: 0, y: 40, filter: "blur(18px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 1.6, ease: "expo.out" }, 0.7);\n' +
 fade_in('#X-s1', 1.1) + fade_in('#X-num', 1.2, 1.0, 20) +
 '      const cnt = { v: 0 }, out = R("#X-v");\n'
 '      tl.fromTo(cnt, { v: 0 }, { v: 5000, duration: 2.0, ease: "expo.out", onUpdate: () => { out.textContent = Math.round(cnt.v).toLocaleString("fr-FR").replace(/\\u202f|\\u00a0/g, " "); } }, 1.2);\n' +
 fade_in('#X-s2', 2.0) + morph_out('X-f', fc, 4.35) + blur_out(['#X-n', '#X-num', '#X-s1', '#X-s2'], 4.3, 0.8))

# ── 05 · Le Monarque (projecteur d'étoiles) ─────────────────────────────────
fh, fj, fo, fc = frame('X-f', 'monarque', 160, 200, 760, 1000, vap={'alpha': 0.22, 'rise': 260}, seed=33)
F['05-monarque'] = ('', fh.replace('</div>\n', '<canvas id="X-st" width="760" height="1000" style="mix-blend-mode:screen"></canvas></div>\n') + '''    <div class="X-a X-c X-i" id="X-n" style="top:1225px; font-size:150px">Le Monarque</div>
    <div class="X-a X-c X-d" id="X-s2" style="top:1415px; font-size:62px">Deux parfums. Un ciel d'étoiles.</div>
    <div class="X-a X-c X-cap" id="X-s1" style="top:1530px">Double recharge · projecteur d'étoiles</div>
''', drive(5.8, [fj, 'AURA.stars(R("#X-st"), { n: 140, band: 0.42, seed: 8 })']) +
 morph_in('X-f', fc, fo, 0.1) + '      tl.fromTo(R("#X-st"), { opacity: 0 }, { opacity: 1, duration: 1.6, ease: "power2.out" }, 1.4);\n'
 '      tl.fromTo(R("#X-n"), { opacity: 0, y: 40, filter: "blur(18px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 1.6, ease: "expo.out" }, 0.9);\n' +
 fade_in('#X-s2', 1.6) + fade_in('#X-s1', 2.0) + morph_out('X-f', fc, 4.35) + blur_out(['#X-n', '#X-s1', '#X-s2'], 4.3, 0.8))

# ── 06 · Nomade / DuoSens / SensPro ────────────────────────────────────────
TRIO = [('nomade', 'Le Nomade', "Jusqu'à 30 jours d'autonomie"), ('duosens', 'DuoSens', 'Maison & voiture · double cartouche'), ('senspro', 'SensPro', 'Diffuseur mural')]
th, tjs, tm = '', '', []
for i, (img, name, spec) in enumerate(TRIO):
    h_, j_, o_, c_ = frame(f'X-f{i}', img, 180, 230, 720, 900, radius=(48, 48, 48, 48), vap={'alpha': 0.24, 'size': 60}, seed=40 + i)
    th += h_ + f'    <div class="X-a X-c X-i" id="X-n{i}" style="top:1170px; font-size:130px">{name}</div>\n    <div class="X-a X-c X-cap" id="X-s{i}" style="top:1360px">{spec}</div>\n'
    if j_: tm.append(j_)
    t0 = 0.05 + i * 1.85
    tjs += (f'      tl.fromTo(R("#X-f{i}"), {{ opacity: 0, x: 140, filter: "blur(18px)", clipPath: "{c_}" }}, {{ opacity: 1, x: 0, filter: "blur(0px)", clipPath: "{o_}", duration: 1.3, ease: "{EXPO}" }}, {t0:.2f});\n'
            f'      tl.fromTo(R("#X-f{i}i"), {{ scale: 1.14 }}, {{ scale: 1.0, duration: 2.6, ease: "power2.out" }}, {t0:.2f});\n'
            f'      tl.fromTo(R("#X-n{i}"), {{ opacity: 0, y: 30, filter: "blur(16px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 1.2, ease: "{EXPO}" }}, {t0 + 0.35:.2f});\n'
            f'      tl.fromTo(R("#X-s{i}"), {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 1.0, ease: "power3.out" }}, {t0 + 0.6:.2f});\n')
    if i < 2:
        te = t0 + 1.55
        tjs += (f'      tl.to(R("#X-f{i}"), {{ opacity: 0, x: -140, filter: "blur(18px)", duration: 0.75, ease: "power3.in" }}, {te:.2f});\n'
                f'      tl.to([R("#X-n{i}"), R("#X-s{i}")], {{ opacity: 0, y: -20, filter: "blur(12px)", duration: 0.6, ease: "power2.in" }}, {te:.2f});\n')
tjs += f'      tl.to([R("#X-f2"), R("#X-n2"), R("#X-s2")], {{ opacity: 0, filter: "blur(14px)", scale: 0.94, duration: 0.8, ease: "power2.in" }}, 4.9);\n'
F['06-trio'] = ('''
    [id^="X-n"], [id^="X-s"] { opacity: 0; }
''', th, drive(6.2, tm) + tjs)

# ── 07 · Six diffuseurs, une signature (ring) ──────────────────────────────
RING = ['prince', 'duchesse', 'monarque', 'nomade', 'duosens', 'senspro']
import math
rh, rj = '', ''
for i, img in enumerate(RING):
    a = -math.pi / 2 + i * 2 * math.pi / 6; cx, cy = 540 + 330 * math.cos(a), 900 + 330 * math.sin(a)
    rh += f'      <div class="X-dot" id="X-d{i}" style="left:{cx - 105:.0f}px; top:{cy - 105:.0f}px"><img src="assets/images/{img}.jpg" alt=""></div>\n'
    rj += f'      tl.fromTo(R("#X-d{i}"), {{ opacity: 0, scale: 0.4, filter: "blur(14px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 1.0, ease: "{EXPO}" }}, {0.15 + i * 0.1:.2f});\n'
F['07-signature'] = ('''
    #X-ring { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; transform-origin: 540px 900px; }
    .X-dot { position: absolute; width: 210px; height: 210px; border-radius: 50%; overflow: hidden; box-shadow: 0 0 0 2px rgba(212,175,55,0.7), 0 0 40px rgba(212,175,55,0.25); }
    .X-dot img { width: 100%; height: 100%; object-fit: cover; display: block; }
    #X-svg { position: absolute; left: 0; top: 0; }
''', '''    <div id="X-ring">
      <svg id="X-svg" width="1080" height="1920"><circle id="X-c" cx="540" cy="900" r="330" fill="none" stroke="%GOLD%" stroke-width="1.5" stroke-opacity="0.8"/></svg>
''' + rh + '''    </div>
    <div class="X-a X-c X-i" id="X-t1" style="top:820px; font-size:74px">Six diffuseurs.</div>
    <div class="X-a X-c X-d" id="X-t2" style="top:905px; font-size:60px; color:%GOLD%">Une signature.</div>
''', '      const C = R("#X-c"), L = 2 * Math.PI * 330;\n'
 '      tl.fromTo(C, { attr: { "stroke-dasharray": L + " " + L, "stroke-dashoffset": L } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.4, ease: "power2.inOut" }, 0.05);\n'
 '      tl.fromTo(R("#X-ring"), { rotation: -20 }, { rotation: 18, duration: 3.4, ease: "none" }, 0);\n' + rj.replace('R("#X-d', 'R("#X-d') +
 blur_in('#X-t1', 0.7, 1.2, 20, 14, 0, False) + blur_in('#X-t2', 0.95, 1.2, 20, 14, 0, False) +
 '      tl.to(R("#X-ring"), { scale: 0.05, opacity: 0, filter: "blur(20px)", duration: 1.0, ease: "power3.in" }, 2.15);\n' +
 blur_out(['#X-t1', '#X-t2'], 2.2, 0.8, -10, 16))

# ── 08 · logo ──────────────────────────────────────────────────────────────
F['08-logo'] = ('''
    #X-logo { position: absolute; left: 250px; top: 520px; width: 580px; }
    #X-orb { left: 90px; top: 380px; width: 900px; height: 600px; }
''', '''    <canvas class="X-cv" id="X-v" width="1080" height="1920"></canvas>
    <div class="X-glow" id="X-orb"></div>
    <img id="X-logo" src="assets/images/sensexpress-logo.png" alt="SensExpress">
    <div class="X-a X-c X-i" id="X-t" style="top:900px; font-size:92px">L'art de parfumer</div>
    <div class="X-a X-c X-i" id="X-t2" style="top:1000px; font-size:92px; color:%GOLD%">vos espaces.</div>
    <div class="X-line" id="X-ln" style="left:390px; top:1150px; width:300px"></div>
    <div class="X-a X-c X-cap" id="X-w" style="top:1200px; color:%CHAMP%; font-size:34px; letter-spacing:0.22em">sensexpress.com</div>
    <div class="X-a X-c X-cap" id="X-p" style="top:1275px; font-size:28px">WhatsApp · +223 70 28 07 07</div>
''', drive(4.2, ['AURA.vapour(R("#X-v"), { x: 540, y: 2000, rise: 1400, size: 280, alpha: 0.10, n: 45, life: 6.0, seed: 9 })']) +
 '      tl.fromTo(R("#X-orb"), { scale: 0.2, opacity: 0 }, { scale: 1, opacity: 1, duration: 1.6, ease: "expo.out" }, 0.0);\n'
 '      tl.fromTo(R("#X-logo"), { opacity: 0, scale: 0.9, filter: "blur(22px)" }, { opacity: 1, scale: 1, filter: "blur(0px)", duration: 1.8, ease: "expo.out" }, 0.2);\n'
 '      tl.fromTo(R("#X-t"), { opacity: 0, y: 30, filter: "blur(18px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 1.6, ease: "expo.out" }, 0.9);\n'
 '      tl.fromTo(R("#X-t2"), { opacity: 0, y: 30, filter: "blur(18px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 1.6, ease: "expo.out" }, 1.15);\n' +
 line_in('#X-ln', 1.4, 1.2) + fade_in('#X-w', 1.7) + fade_in('#X-p', 1.95))

def scene(fid, dur, css, html, js):
    pre = 's' + fid[:2]
    def sub(s):
        s = s.replace('X-', pre + '-')
        for k, v in TOK.items(): s = s.replace(k, v)
        return s
    return f'''<template>
  <style>
{FONTS}
    #root {{ position: absolute; inset: 0; width: 100%; height: 100%; overflow: hidden; background: transparent; }}
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
    open(f'{P}/compositions/frames/{fid}.html', 'w').write(scene(fid, dur, css, html, js))
    scenes += f'      <div id="el-{fid}" class="scene" data-composition-id="{fid}" data-composition-src="compositions/frames/{fid}.html" data-start="{st}" data-duration="{dur}" data-track-index="{1 + i % 2}"></div>\n'
    if i > 0:
        trans += f'        tl.fromTo("#el-{fid}", {{ opacity: 0 }}, {{ opacity: 1, duration: {OV}, ease: "power2.inOut" }}, {st});\n'
breaths = ''.join(f'      <audio id="br{i}" src="assets/breath.wav" data-start="{round(st - 0.3, 2)}" data-duration="1.1" data-track-index="{12 + i % 3}" data-volume="0.22"></audio>\n' for i, (fid, st, ln) in enumerate(SC) if st > 0)
VOJ = f'{P}/assets/voice/voice.json'
voice = os.path.exists(VOJ)
vo = ''.join(f'      <audio id="vo{i}" src="{s}" data-start="{a}" data-duration="{d}" data-track-index="{30 + i}" data-volume="1"></audio>\n' for i, (s, a, d) in enumerate(json.load(open(VOJ)))) if voice else ''
idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/aura.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #08080C; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #08080C; }}
      .scene {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
      #bg {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
      #vig {{ position: absolute; inset: 0; background: radial-gradient(80% 60% at 50% 45%, rgba(8,8,12,0) 50%, rgba(8,8,12,0.7) 100%); pointer-events: none; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
      <canvas id="bg" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" width="{W}" height="{H}"></canvas>
      <div id="vig" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="9"></div>
{scenes}      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="11" data-volume="{0.4 if voice else 0.85}"></audio>
{breaths}{vo}    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
      (function () {{ var tl = window.__timelines["main"];
        var bg = AURA.backdrop(document.getElementById("bg"), {{ seed: 5, dust: 150 }});
        var p = {{ t: 0 }};
        tl.fromTo(p, {{ t: 0 }}, {{ t: {TOTAL}, duration: {TOTAL}, ease: "none", onUpdate: function () {{ bg(p.t, Math.min(1, p.t / 1.5 + 0.25)); }} }}, 0);
        bg(0, 0.25);
{trans}        tl.to({{}}, {{ duration: {TOTAL} }}, 0);
      }})();
    </script>
  </body>
</html>
'''
open(f'{P}/index.html', 'w').write(idx)
print('ok', TOTAL)
