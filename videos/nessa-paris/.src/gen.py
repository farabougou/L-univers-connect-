# Nessa Paris — film de marque 39 s, vertical 1080×1920, 25 i/s.
# Direction : luxe sensoriel (Apple / Aesop / Diptyque). Fond noir #08080C toujours vivant (halos dorés, poussière,
# reflet lent — assets/vendor/aura.js), brume qui monte en ondulant et se dissipe, fils de soie dorés, typo à flou
# cinétique, fenêtres photo qui se transforment d'une scène à l'autre. Photos : nessaparisbeauty.com (sans retouche IA).
# Textes produits repris des fiches du site, sans prix.
import os, json, math
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, OV = 1080, 1920, 0.6
TOK = {'%BG%': '#08080C', '%GOLD%': '#D4AF37', '%CHAMP%': '#F5E6D3', '%MUTE%': '#B9AE9E'}
SC = [('01-eveil', 0.0, 5.0), ('02-lumiere', 5.0, 4.2), ('03-softglow', 9.2, 5.6), ('04-nature', 14.8, 5.6),
      ('05-intense', 20.4, 5.2), ('06-visage', 25.6, 5.6), ('07-bridal', 31.2, 4.2), ('08-logo', 35.4, 3.8)]
TOTAL = round(SC[-1][1] + SC[-1][2], 2)
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
    .X-word { position: absolute; left: 0; right: 0; text-align: center; font-family: "Cormorant"; font-weight: 500; color: %CHAMP%; white-space: nowrap; line-height: 1; }
    .X-word span { display: inline-block; }
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
def name_in(sel, at, d=1.6):
    return f'      tl.fromTo(R("{sel}"), {{ opacity: 0, y: 40, filter: "blur(18px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: {d}, ease: "{EXPO}" }}, {at});\n'
def wordmark(wid, top, size, gap=0.24):
    """NESSA set letter by letter (the tracking closes in by moving the letters, never by tweening letter-spacing)."""
    ls = ''.join(f'<span id="{wid}{k}" style="margin: 0 {gap / 2:.2f}em">{c}</span>' for k, c in enumerate('NESSA'))
    return f'    <div class="X-word" id="{wid}" style="top:{top}px; font-size:{size}px">{ls}</div>\n'
def wordmark_in(wid, at, spread=70):
    return ''.join(f'      tl.fromTo(R("#{wid}{k}"), {{ opacity: 0, x: {(k - 2) * spread}, filter: "blur(22px)" }}, {{ opacity: 1, x: 0, filter: "blur(0px)", duration: 2.2, ease: "{EXPO}" }}, {at + abs(k - 2) * 0.12:.2f});\n' for k in range(5))
def mist(cid, o, front=False):
    """Full-frame vapour canvas: puffs rise from o.x/o.y, undulate on layered turbulence, swell and dissipate."""
    return f'    <canvas class="X-cv" id="{cid}" width="{W}" height="{H}"{' style="z-index:4"' if front else ''}></canvas>\n', f'AURA.vapour(R("#{cid}"), {json.dumps(o)})'

ARCH = (380, 380, 40, 40)
def frame(fid, img, x, y, w, h, radius=ARCH, vap=None, seed=11):
    """Photo window with a warm steam veil rising from its base."""
    r = ' '.join(f'{v}px' for v in radius)
    html = f'    <div class="X-frame" id="{fid}" style="left:{x}px; top:{y}px; width:{w}px; height:{h}px; border-radius:{r}"><img id="{fid}i" src="assets/images/{img}.jpg" alt="">'
    js = ''
    if vap is not False:
        html += f'<canvas id="{fid}v" width="{w}" height="{h}"></canvas>'
        o = {'x': w / 2, 'y': h * 1.02, 'rise': round(h * 0.9), 'size': round(w * 0.3), 'alpha': 0.1, 'n': 50, 'life': 5.5, 'sx': round(w * 0.8), 'fin': 0.3, 'seed': seed}
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
    makers = [m for m in makers if m]
    if not makers: return ''
    lines = ''.join(f'      const __r{i} = {m};\n' for i, m in enumerate(makers))
    calls = '; '.join(f'__r{i}(__p.t)' for i in range(len(makers)))
    return lines + f'''      const __p = {{ t: 0 }};
      tl.fromTo(__p, {{ t: 0 }}, {{ t: {dur}, duration: {dur}, ease: "none", onUpdate: () => {{ {calls}; }} }}, 0);
      {calls};
'''
def dur_of(fid):
    i = [s[0] for s in SC].index(fid); return round(SC[i][2] + (OV if i < len(SC) - 1 else 0), 2)

F = {}
# ── 01 · Éveil : une goutte de lumière tombe, l'onde fait naître NESSA ─────────
mh, mj = mist('X-v', {'x': 540, 'y': 2050, 'rise': 1550, 'size': 360, 'alpha': 0.085, 'n': 80, 'life': 7.0, 'sx': 1000, 'fin': 0.3, 'seed': 4})
rip = ''.join(f'<ellipse id="X-r{k}" cx="540" cy="1090" rx="420" ry="64" fill="none" stroke="%GOLD%" stroke-width="{2 - k * 0.5}"/>' for k in range(3))
F['01-eveil'] = ('''
    #X-orb { left: 90px; top: 560px; width: 900px; height: 900px; }
    #X-drop { position: absolute; left: 524px; top: 1074px; width: 32px; height: 32px; border-radius: 50%;
      background: radial-gradient(circle at 40% 35%, #FFF6E2, %GOLD% 55%, rgba(212,175,55,0.2)); box-shadow: 0 0 30px rgba(212,175,55,0.9), 0 0 90px rgba(212,175,55,0.5); }
    #X-svg { position: absolute; left: 0; top: 0; }
''', mh + f'''    <div class="X-glow" id="X-orb"></div>
    <svg id="X-svg" width="1080" height="1920">{rip}</svg>
    <div id="X-drop"></div>
''' + wordmark('X-nm', 720, 200) + '''    <div class="X-a X-c X-cap" id="X-p" style="top:950px; font-size:30px; letter-spacing:0.9em; padding-left:0.9em">Paris</div>
    <div class="X-a X-c X-i" id="X-t" style="top:1200px; font-size:66px">Soins visage &amp; corps</div>
''', drive(dur_of('01-eveil'), [mj]) +
 '      tl.fromTo(R("#X-drop"), { y: -1180, scaleY: 1.7, opacity: 0 }, { y: 0, scaleY: 1, opacity: 1, duration: 1.05, ease: "power3.in" }, 0.15);\n'
 '      tl.to(R("#X-drop"), { scale: 0, opacity: 0, duration: 0.5, ease: "power2.out" }, 1.2);\n' +
 ''.join(f'      tl.fromTo(R("#X-r{k}"), {{ attr: {{ rx: 6, ry: 1 }}, opacity: 0.9 }}, {{ attr: {{ rx: 420, ry: 64 }}, opacity: 0, duration: 2.6, ease: "{EXPO}" }}, {1.2 + k * 0.22:.2f});\n' for k in range(3)) +
 '      tl.fromTo(R("#X-orb"), { scale: 0.1, opacity: 0 }, { scale: 1, opacity: 1, duration: 3.0, ease: "power2.out" }, 1.15);\n' +
 wordmark_in('X-nm', 1.45) + fade_in('#X-p', 2.3, 1.4, 0) + name_in('#X-t', 2.9, 1.5) +
 blur_out(['#X-nm', '#X-p', '#X-t'], 4.15, 1.0, -60, 22) +
 '      tl.to(R("#X-orb"), { opacity: 0, scale: 1.3, duration: 1.2, ease: "power2.in" }, 4.3);\n')

# ── 02 · Votre peau a sa propre lumière — fils de soie ──────────────────────
F['02-lumiere'] = ('', f'''    <canvas class="X-cv" id="X-s" width="{W}" height="{H}"></canvas>
''' + words('Votre peau', 'X-d', 'top:690px; font-size:120px', 'X-l1') +
 words('a sa propre', 'X-d', 'top:820px; font-size:120px', 'X-l2') +
 words('lumière.', 'X-i', 'top:960px; font-size:180px; color:%GOLD%', 'X-l3') +
 '    <div class="X-line" id="X-ln" style="left:390px; top:1200px; width:300px"></div>\n',
 drive(dur_of('02-lumiere'), ['AURA.silk(R("#X-s"), { y: 980, spread: 520, n: 4, alpha: 0.13, seed: 12 })']) +
 '      tl.fromTo(R("#X-s"), { opacity: 0 }, { opacity: 1, duration: 1.6, ease: "power2.out" }, 0);\n' +
 blur_in('#X-l1', 0.35) + blur_in('#X-l2', 0.9) + blur_in('#X-l3', 1.5, 1.8, 40, 22) + line_in('#X-ln', 2.1, 1.4) +
 blur_out(['#X-l1', '#X-l2', '#X-l3', '#X-ln'], 3.6, 0.9) +
 '      tl.to(R("#X-s"), { opacity: 0, duration: 1.0, ease: "power2.in" }, 3.7);\n')

# ── 03 · Soft Glow ─────────────────────────────────────────────────────────
mh, mj = mist('X-m', {'x': 540, 'y': 1300, 'rise': 1200, 'size': 300, 'alpha': 0.075, 'n': 64, 'life': 6.5, 'sx': 800, 'fin': 0.3, 'seed': 21})
fh, fj, fo, fc = frame('X-f', 'softglow', 160, 200, 760, 1000, seed=22)
F['03-softglow'] = ('', mh + fh + '''    <div class="X-a X-c X-i" id="X-n" style="top:1225px; font-size:150px">Soft Glow</div>
    <div class="X-a X-c X-cap" id="X-s1" style="top:1430px">Papaye · Niacinamide · Acide kojique</div>
    <div class="X-a X-c X-d" id="X-s2" style="top:1490px; font-size:64px">Une peau plus nette, plus lumineuse.</div>
''', drive(dur_of('03-softglow'), [mj, fj]) + morph_in('X-f', fc, fo, 0.1) + name_in('#X-n', 0.9) +
 fade_in('#X-s1', 1.6) + fade_in('#X-s2', 2.4) + morph_out('X-f', fc, 4.95) + blur_out(['#X-n', '#X-s1', '#X-s2'], 4.9, 0.8))

# ── 04 · Le meilleur de la nature : trois orbes d'ingrédients dans la brume ──
ORBS = [('papaye', 'Papaye', 205, 900), ('carotte', 'Carotte', 540, 1060), ('curcuma', 'Curcuma', 875, 900)]
oh, oj = '', ''
for i, (img, lab, cx, cy) in enumerate(ORBS):
    oh += (f'    <div class="X-orbi" id="X-o{i}" style="left:{cx - 125}px; top:{cy - 125}px"><img src="assets/images/{img}.jpg" alt=""></div>\n'
           f'    <div class="X-a X-i" id="X-ol{i}" style="left:{cx - 200}px; width:400px; text-align:center; top:{cy + 150}px; font-size:64px">{lab}</div>\n')
    t0 = 0.7 + i * 0.35
    oj += (f'      tl.fromTo(R("#X-o{i}"), {{ opacity: 0, scale: 0.3, filter: "blur(18px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 1.8, ease: "elastic.out(1, 0.75)" }}, {t0:.2f});\n'
           f'      tl.fromTo(R("#X-o{i}"), {{ y: 0 }}, {{ y: -26, duration: 1.7, ease: "sine.inOut", yoyo: true, repeat: 1 }}, {t0 + 0.6:.2f});\n'
           f'      tl.fromTo(R("#X-ol{i}"), {{ opacity: 0, y: 20, filter: "blur(12px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 1.2, ease: "{EXPO}" }}, {t0 + 0.35:.2f});\n')
mh, mj = mist('X-m', {'x': 540, 'y': 2050, 'rise': 1550, 'size': 360, 'alpha': 0.08, 'n': 80, 'life': 7.0, 'sx': 1000, 'fin': 0.3, 'seed': 31})
F['04-nature'] = ('''
    .X-orbi { position: absolute; width: 250px; height: 250px; border-radius: 50%; overflow: hidden;
      box-shadow: 0 0 0 2px rgba(212,175,55,0.75), 0 0 60px rgba(212,175,55,0.35), 0 0 140px rgba(212,175,55,0.15); }
    .X-orbi img { width: 100%; height: 100%; object-fit: cover; display: block; }
    #X-svg { position: absolute; left: 0; top: 0; }
''', mh + '''    <svg id="X-svg" width="1080" height="1920"><path id="X-arc" d="M 205 900 Q 540 1230 875 900" fill="none" stroke="%GOLD%" stroke-width="1.2" stroke-opacity="0.7"/></svg>
''' + words('Le meilleur', 'X-d', 'top:340px; font-size:110px', 'X-h1') + words('de la nature', 'X-i', 'top:465px; font-size:140px; color:%GOLD%', 'X-h2') +
 oh + words('au service de votre éclat.', 'X-i', 'top:1520px; font-size:72px', 'X-h3'),
 drive(dur_of('04-nature'), [mj]) + blur_in('#X-h1', 0.2) + blur_in('#X-h2', 0.6, 1.6) +
 '      const A = R("#X-arc"), AL = A.getTotalLength();\n'
 '      tl.fromTo(A, { attr: { "stroke-dasharray": AL + " " + AL, "stroke-dashoffset": AL } }, { attr: { "stroke-dashoffset": 0 }, duration: 2.2, ease: "power2.inOut" }, 0.8);\n' +
 oj + blur_in('#X-h3', 2.6, 1.4, 24, 14, 0.08) +
 blur_out(['#X-h1', '#X-h2', '#X-o0', '#X-o1', '#X-o2', '#X-ol0', '#X-ol1', '#X-ol2', '#X-h3', '#X-svg'], 4.9, 0.85, -40, 18))

# ── 05 · Intense Glow Skin ─────────────────────────────────────────────────
mh, mj = mist('X-m', {'x': 540, 'y': 1200, 'rise': 1100, 'size': 280, 'alpha': 0.075, 'n': 64, 'life': 6.5, 'sx': 760, 'fin': 0.3, 'seed': 41})
fh, fj, fo, fc = frame('X-f', 'intense', 190, 180, 700, 900, radius=(44, 44, 44, 44), seed=42)
F['05-intense'] = ('', mh + fh + '''    <div class="X-a X-c X-i" id="X-n" style="top:1110px; font-size:124px">Intense Glow Skin</div>
    <div class="X-a X-c X-d" id="X-s2" style="top:1270px; font-size:70px; color:%GOLD%">La version intense.</div>
    <div class="X-a X-c X-cap" id="X-s1" style="top:1385px">Carotte · Alpha-arbutine · Collagène</div>
''', drive(dur_of('05-intense'), [mj, fj]) + morph_in('X-f', fc, fo, 0.1) + name_in('#X-n', 0.8) +
 fade_in('#X-s2', 1.6) + fade_in('#X-s1', 2.3) + morph_out('X-f', fc, 4.55) + blur_out(['#X-n', '#X-s1', '#X-s2'], 4.5, 0.8))

# ── 06 · Le rituel visage : Nettoyer · Réparer · Hydrater ───────────────────
TRIO = [('nila', 'Nettoyer', 'Savon Nila', 0.3), ('perfectskin', 'Réparer', 'Perfect Skin', 1.0), ('hydra', 'Hydrater', 'Hydra Face Cream', 1.7)]
th, tjs, tm = '', '', []
for i, (img, step, prod, t0) in enumerate(TRIO):
    x = 40 + i * 340
    h_, j_, o_, c_ = frame(f'X-f{i}', img, x, 520, 320, 520, radius=(160, 160, 22, 22), vap={'size': 110, 'n': 34, 'alpha': 0.13}, seed=50 + i)
    th += h_ + (f'    <div class="X-a X-i" id="X-n{i}" style="left:{x}px; width:320px; text-align:center; top:1060px; font-size:66px">{step}</div>\n'
                f'    <div class="X-a X-cap" id="X-s{i}" style="left:{x}px; width:320px; text-align:center; top:1150px; font-size:18px; letter-spacing:0.24em">{prod}</div>\n')
    tm.append(j_)
    tjs += (f'      tl.fromTo(R("#X-f{i}"), {{ opacity: 0, y: 60, filter: "blur(16px)", clipPath: "{c_}" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", clipPath: "{o_}", duration: 1.5, ease: "{EXPO}" }}, {t0:.2f});\n'
            f'      tl.fromTo(R("#X-f{i}i"), {{ scale: 1.2 }}, {{ scale: 1.0, duration: 4.5, ease: "power2.out" }}, {t0:.2f});\n'
            f'      tl.fromTo(R("#X-n{i}"), {{ opacity: 0, y: 24, filter: "blur(14px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 1.2, ease: "{EXPO}" }}, {t0 + 0.25:.2f});\n'
            f'      tl.fromTo(R("#X-s{i}"), {{ opacity: 0, y: 12 }}, {{ opacity: 1, y: 0, duration: 1.0, ease: "power3.out" }}, {t0 + 0.5:.2f});\n')
th = words('Le rituel visage', 'X-i', 'top:300px; font-size:110px', 'X-t') + th
th += words('Plus nette. Plus lumineuse.', 'X-d', 'top:1300px; font-size:72px', 'X-cl')
th += '    <div class="X-line" id="X-ln" style="left:390px; top:1430px; width:300px"></div>\n'
tjs = blur_in('#X-t', 0.0, 1.5, 30, 16, 0.12) + tjs + blur_in('#X-cl', 2.9, 1.4, 24, 14, 0.09) + line_in('#X-ln', 3.3, 1.2)
tjs += blur_out(['#X-t', '#X-f0', '#X-f1', '#X-f2', '#X-n0', '#X-n1', '#X-n2', '#X-s0', '#X-s1', '#X-s2', '#X-cl', '#X-ln'], 4.9, 0.8, -20, 16)
F['06-visage'] = ('''
    [id^="X-n"], [id^="X-s"] { opacity: 0; }
''', th, drive(dur_of('06-visage'), tm) + tjs)

# ── 07 · Bridal Glow Ritual ────────────────────────────────────────────────
mh, mj = mist('X-m', {'x': 540, 'y': 1450, 'rise': 1350, 'size': 320, 'alpha': 0.075, 'n': 64, 'life': 6.5, 'sx': 900, 'fin': 0.3, 'seed': 61})
fh, fj, fo, fc = frame('X-f', 'bridal', 110, 260, 860, 1020, radius=(430, 430, 40, 40), seed=62)
F['07-bridal'] = ('', mh + fh + '''    <div class="X-a X-c X-i" id="X-n" style="top:1290px; font-size:116px">Bridal Glow Ritual</div>
    <div class="X-a X-c X-d" id="X-s2" style="top:1430px; font-size:66px">Le rituel des grands jours.</div>
    <div class="X-a X-c X-cap" id="X-s1" style="top:1540px">Visage &amp; corps · 4 soins</div>
''', drive(dur_of('07-bridal'), [mj, fj]) + morph_in('X-f', fc, fo, 0.1, 1.6) + name_in('#X-n', 0.7) +
 fade_in('#X-s2', 1.4) + fade_in('#X-s1', 2.0) + morph_out('X-f', fc, 3.55) + blur_out(['#X-n', '#X-s1', '#X-s2'], 3.5, 0.8))

# ── 08 · signature ─────────────────────────────────────────────────────────
mh, mj = mist('X-v', {'x': 540, 'y': 2050, 'rise': 1500, 'size': 360, 'alpha': 0.085, 'n': 80, 'life': 7.0, 'sx': 1000, 'fin': 0.3, 'seed': 9})
F['08-logo'] = ('''
    #X-orb { left: 90px; top: 380px; width: 900px; height: 700px; }
''', mh + '''    <div class="X-glow" id="X-orb"></div>
''' + wordmark('X-nm', 560, 190) + '''    <div class="X-a X-c X-cap" id="X-p" style="top:780px; font-size:30px; letter-spacing:0.9em; padding-left:0.9em">Paris</div>
    <div class="X-a X-c X-i" id="X-t" style="top:930px; font-size:96px; color:%GOLD%">Révélez votre éclat.</div>
    <div class="X-line" id="X-ln" style="left:390px; top:1090px; width:300px"></div>
    <div class="X-a X-c X-cap" id="X-w" style="top:1140px; color:%CHAMP%; font-size:34px; letter-spacing:0.16em; text-transform:none">nessaparisbeauty.com</div>
    <div class="X-a X-c X-cap" id="X-k" style="top:1215px; font-size:24px">Soins visage &amp; corps</div>
''', drive(dur_of('08-logo'), [mj]) +
 '      tl.fromTo(R("#X-orb"), { scale: 0.2, opacity: 0 }, { scale: 1, opacity: 1, duration: 1.8, ease: "expo.out" }, 0.0);\n' +
 wordmark_in('X-nm', 0.15, 50) + fade_in('#X-p', 0.8, 1.2, 0) + name_in('#X-t', 1.1) +
 line_in('#X-ln', 1.5, 1.2) + fade_in('#X-w', 1.8) + fade_in('#X-k', 2.05))

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
    dur = dur_of(fid)
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
{scenes}      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="11" data-volume="{0.24 if voice else 0.85}"></audio>
{breaths}{vo}    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
      (function () {{ var tl = window.__timelines["main"];
        var bg = AURA.backdrop(document.getElementById("bg"), {{ seed: 17, dust: 160 }});
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
