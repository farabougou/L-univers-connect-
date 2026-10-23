# Nessa Paris — film de marque 39,5 s, vertical 1080×1920, 25 i/s. Version 2 : passe de polish studio.
# Direction : luxe sensoriel (Apple / Aesop / Diptyque). Fond noir #08080C toujours vivant (halos dorés, poussière,
# reflet lent — assets/vendor/aura.js), brume qui monte en ondulant et se dissipe, fils de soie dorés.
# Polish (skill studio-polish-pass, système videos/_studio) : caméra 2.5D par scène (calques fond / sujet / premier
# plan / texte, parallaxe, mise au point du premier plan vers le produit), poussière d'or floue au premier plan,
# noms découpés lettre par lettre depuis le centre, ressorts au lieu de rebonds, vie continue sur chaque élément tenu,
# reflet qui traverse chaque photo, sorties qui chevauchent l'entrée suivante (plus de passage au noir), goutte
# avec flou de mouvement, grain de film. Contenu, photos et calage sur la voix identiques à la v1 (.src/gen_v1.py).
import os, json, random
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, OV = 1080, 1920, 0.6
TOK = {'%BG%': '#08080C', '%GOLD%': '#D4AF37', '%CHAMP%': '#F5E6D3', '%MUTE%': '#B9AE9E'}
# scene timing follows the voiceover (.src/vo.py): each sentence lands in its scene, every word on its visual
SC = [('01-eveil', 0.0, 4.6), ('02-lumiere', 4.6, 3.6), ('03-softglow', 8.2, 6.3), ('04-nature', 14.5, 5.8),
      ('05-intense', 20.3, 5.6), ('06-visage', 25.9, 5.3), ('07-bridal', 31.2, 4.4), ('08-logo', 35.6, 3.9)]
TOTAL = round(SC[-1][1] + SC[-1][2], 2)
EXIT = 0.2  # sorties lancées 0,2 s avant la scène suivante : elles se croisent avec son entrée

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
    .X-bk { position: absolute; border-radius: 50%; }
    .X-gold { --st-glow: rgba(212,175,55,0.45); }
'''

# ── texte ──────────────────────────────────────────────────────────────────
def words(text, cls, style, wid, extra=''):
    ws = ''.join(f'<span class="X-w">{w}</span>' + (' ' if k < len(text.split(' ')) - 1 else '') for k, w in enumerate(text.split(' ')))
    return f'    <div class="X-a X-c {cls}" id="{wid}" style="{style}" {extra}>{ws}</div>\n'
def words_in(sel, at, d=1.5, y=34, blur=14, st=0.1):
    """Mots qui montent avec flou, décalés (preset luxe)."""
    return f'      S.rise(tl, RA("{sel} .X-w"), {at}, {{ y: {y}, blur: {blur}, stagger: {st}, duration: {d} }});\n'
def chars_in(sel, at, d=1.7, y=46, blur=16, st=0.04, frm='center'):
    """Nom découpé lettre par lettre, depuis le centre : le mot se forme au lieu d'apparaître en bloc."""
    return f'      S.rise(tl, S.split(R("{sel}")), {at}, {{ y: {y}, blur: {blur}, stagger: {st}, duration: {d}, from: "{frm}", max: 0.7 }});\n'
def soft_in(sel, at, d=1.3, y=16, blur=8):
    return f'      S.rise(tl, R("{sel}"), {at}, {{ y: {y}, blur: {blur}, duration: {d} }});\n'
def line_in(sel, at, d=1.3):
    return f'      tl.fromTo(R("{sel}"), {{ scaleX: 0, opacity: 0 }}, {{ scaleX: 1, opacity: 1, duration: {d}, ease: S.ease.silk }}, {at});\n'
def leave(sels, at, d=0.75, y=-44, blur=18):
    q = '[' + ', '.join(f'R("{s}")' for s in sels) + ']'
    return f'      S.leave(tl, {q}, {at:.2f}, {{ y: {y}, blur: {blur}, duration: {d}, ease: S.ease.accel }});\n'
def wordmark(wid, top, size, gap=0.24):
    """NESSA lettre par lettre (le resserrement se fait en déplaçant les lettres, jamais avec letter-spacing)."""
    ls = ''.join(f'<span id="{wid}{k}" style="margin: 0 {gap / 2:.2f}em">{c}</span>' for k, c in enumerate('NESSA'))
    return f'    <div class="X-word" id="{wid}" style="top:{top}px; font-size:{size}px">{ls}</div>\n'
def wordmark_in(wid, at, spread=70):
    return f'      S.converge(tl, [{", ".join(f"R({chr(34)}#{wid}{k}{chr(34)})" for k in range(5))}], {at}, {{ spread: {spread}, blur: 22, duration: 2.2, stagger: 0.12 }});\n'

# ── matière : brume, poussière d'or, halo ───────────────────────────────────
def mist(cid, o):
    """Brume plein cadre : bouffées qui montent, ondulent sur une turbulence en couches, gonflent et se dissipent."""
    return f'      <canvas class="X-cv" id="{cid}" width="{W}" height="{H}"></canvas>\n', f'AURA.vapour(R("#{cid}"), {json.dumps(o)})'
def dust(seed, n=12, keep=(250, 300, 830, 1500)):
    """Poussière d'or au premier plan : disques doux placés hors de la zone du produit (la caméra les floute)."""
    r, out, k = random.Random(seed), '', 0
    while k < n:
        x, y, d = r.uniform(-60, 1100), r.uniform(40, 1880), r.uniform(40, 150)
        if keep[0] - d < x < keep[2] and keep[1] - d < y < keep[3]: continue
        a, c = r.uniform(0.32, 0.6), ('212,175,55' if r.random() < 0.6 else '245,230,211')
        out += f'      <i class="X-bk" style="left:{x:.0f}px; top:{y:.0f}px; width:{d:.0f}px; height:{d:.0f}px; background: radial-gradient(circle, rgba({c},{a:.2f}), rgba({c},0) 70%)"></i>\n'
        k += 1
    return out
def halo(hid, x, y, w, h):
    return f'      <div class="X-glow" id="{hid}" style="left:{x}px; top:{y}px; width:{w}px; height:{h}px"></div>\n'
def breathe(sel, at, dur, lo=0.92, hi=1.06, period=2.6):
    n = max(1, int(dur / period))
    return f'      tl.fromTo(R("{sel}"), {{ scale: {lo}, opacity: 0.75 }}, {{ scale: {hi}, opacity: 1, duration: {period}, ease: S.ease.breath, yoyo: true, repeat: {n - 1} }}, {at});\n'

# ── caméra 2.5D ────────────────────────────────────────────────────────────
def stage(bg='', mid='', fg='', txt=''):
    return (f'    <div class="st-stage">\n    <div class="st-layer" id="X-Lbg">\n{bg}    </div>\n    <div class="st-layer" id="X-Lmid">\n{mid}    </div>\n'
            f'    <div class="st-layer" id="X-Lfg">\n{fg}    </div>\n    </div>\n    <div class="st-layer" id="X-Ltxt">\n{txt}    </div>\n')
def camera(fid, keys, depths=(0.35, 1, 1.7, 0.45), dof=True):
    ks = ', '.join('{ ' + ', '.join((f'ease: S.ease.{v}' if k == 'ease' else f'{k}: {v}') for k, v in key.items()) + ' }' for key in keys)
    ly = (f'[{{ el: R("#X-Lbg"), depth: {depths[0]} }}, {{ el: R("#X-Lmid"), depth: {depths[1]} }}, '
          f'{{ el: R("#X-Lfg"), depth: {depths[2]} }}, {{ el: R("#X-Ltxt"), depth: {depths[3]}, blur: false }}]')
    return (f'      S.camera(tl, {ly}, {{ start: 0, end: {dur_of(fid)}, {"dof: { k: 9, max: 12 }, " if dof else ""}'
            f'drift: {{ x: 4, y: 4, r: 0.08, period: 9 }}, keys: [{ks}] }});\n')
def dust_life(dur):
    return f'      S.life(tl, RA(".X-bk"), 0, {dur}, {{ x: 12, y: 16, rotate: 0, scale: 0.03, period: 7, seed: 5 }});\n'

# ── fenêtres photo ─────────────────────────────────────────────────────────
ARCH = (380, 380, 40, 40)
def frame(fid, img, x, y, w, h, radius=ARCH, vap=None, seed=11):
    """Fenêtre photo : voile de vapeur qui monte de sa base, reflet prêt à traverser."""
    r = ' '.join(f'{v}px' for v in radius)
    html = (f'      <div class="X-frame" id="{fid}" style="left:{x}px; top:{y}px; width:{w}px; height:{h}px; border-radius:{r}">'
            f'<img id="{fid}i" src="assets/images/{img}.jpg" alt="">')
    o = {'x': w / 2, 'y': h * 1.02, 'rise': round(h * 0.9), 'size': round(w * 0.3), 'alpha': 0.1, 'n': 50, 'life': 5.5, 'sx': round(w * 0.8), 'fin': 0.3, 'seed': seed}
    if vap: o.update(vap)
    html += f'<canvas id="{fid}v" width="{w}" height="{h}"></canvas><div class="st-sheen" id="{fid}sh"></div></div>\n'
    return html, f'AURA.vapour(R("#{fid}v"), {json.dumps(o)})', f'inset(0% 0% 0% 0% round {r})', f'inset(40% 34% 40% 34% round {w}px {w}px {w}px {w}px)'
def morph_in(fid, closed, open_, at, d=1.8):
    return (f'      tl.fromTo(R("#{fid}"), {{ clipPath: "{closed}", opacity: 0 }}, {{ clipPath: "{open_}", opacity: 1, duration: {d}, ease: S.ease.silk }}, {at});\n'
            f'      tl.fromTo(R("#{fid}i"), {{ scale: 1.18, filter: "blur(10px) brightness(0.7)" }}, {{ scale: 1.0, filter: "blur(0px) brightness(1)", duration: {d + 2.6}, ease: "power2.out" }}, {at});\n')
def morph_out(fid, closed, at, d=0.75):
    return f'      tl.fromTo(R("#{fid}"), {{ filter: "blur(0px)" }}, {{ clipPath: "{closed}", opacity: 0, filter: "blur(10px)", duration: {d}, ease: S.ease.accel, immediateRender: false }}, {at:.2f});\n'
def drive(dur, makers):
    """Un seul pilote fait avancer tous les rendus canvas avec le temps de la scène (seek-safe)."""
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
def out_at(fid):
    i = [s[0] for s in SC].index(fid); return round(SC[i][2] - EXIT, 2)

F = {}
# ── 01 · Éveil : une goutte de lumière tombe (flou de mouvement), l'onde fait naître NESSA ─────────
fid = '01-eveil'
mh, mj = mist('X-v', {'x': 540, 'y': 2050, 'rise': 1550, 'size': 360, 'alpha': 0.085, 'n': 80, 'life': 7.0, 'sx': 1000, 'fin': 0.3, 'seed': 4})
rip = ''.join(f'<ellipse id="X-r{k}" cx="540" cy="1090" rx="420" ry="64" fill="none" stroke="%GOLD%" stroke-width="{2 - k * 0.5}"/>' for k in range(3))
F[fid] = ('''
    #X-orb { left: 90px; top: 560px; width: 900px; height: 900px; }
    #X-drop { position: absolute; left: 520px; top: 1070px; width: 40px; height: 40px; border-radius: 50%;
      background: radial-gradient(circle at 40% 35%, #FFF6E2, %GOLD% 55%, rgba(212,175,55,0.2)); box-shadow: 0 0 30px rgba(212,175,55,0.9), 0 0 90px rgba(212,175,55,0.5); }
    #X-svg { position: absolute; left: 0; top: 0; }
''', stage(bg=mh + halo('X-orb', 90, 560, 900, 900),
           mid=f'      <svg id="X-svg" width="1080" height="1920">{rip}</svg>\n      <div id="X-drop" data-hf-motion-blur></div>\n',
           fg=dust(1, 9),
           txt=wordmark('X-nm', 720, 200) + '''    <div class="X-a X-c X-cap" id="X-p" style="top:950px; font-size:30px; letter-spacing:0.9em; padding-left:0.9em">Paris</div>
    <div class="X-a X-c X-i" id="X-t" style="top:1200px; font-size:66px">Soins visage &amp; corps</div>
'''),
 drive(dur_of(fid), [mj]) + dust_life(dur_of(fid)) +
 camera(fid, [{'t': 0, 's': 1.1, 'y': 60, 'rx': 6, 'f': 1.7}, {'t': 1.3, 's': 1.02, 'y': 0, 'rx': 0, 'f': 1.0, 'ease': 'silk'}, {'t': dur_of(fid), 's': 1.06, 'ease': 'breath'}]) +
 '      tl.fromTo(R("#X-orb"), { scale: 0.35, opacity: 0.25 }, { scale: 1, opacity: 1, duration: 3.0, ease: S.ease.silk }, 1.1);\n'
 '      tl.fromTo(R("#X-drop"), { y: -1180, scaleY: 1.8, opacity: 0 }, { y: 0, scaleY: 1, opacity: 1, duration: 1.1, ease: "power2.in" }, 0.05);\n'
 '      tl.to(R("#X-drop"), { scaleX: 1.9, scaleY: 0.35, opacity: 0, duration: 0.45, ease: S.ease.silk }, 1.15);\n' +
 ''.join(f'      tl.fromTo(R("#X-r{k}"), {{ attr: {{ rx: 6, ry: 1 }}, opacity: 0.9 }}, {{ attr: {{ rx: 420, ry: 64 }}, opacity: 0, duration: 2.6, ease: S.ease.silk }}, {1.15 + k * 0.2:.2f});\n' for k in range(3)) +
 wordmark_in('X-nm', 1.3) + soft_in('#X-p', 1.9, 1.4, 0, 6) + words_in('#X-t', 2.55, 1.4, 24, 12, 0.08).replace('RA("#X-t .X-w")', 'S.split(R("#X-t"), { by: "words" })') +
 leave(['#X-nm', '#X-p', '#X-t'], out_at(fid) - 0.45, 0.75, -60, 22) +
 f'      tl.to(R("#X-orb"), {{ opacity: 0, scale: 1.3, duration: 0.8, ease: S.ease.accel }}, {out_at(fid)});\n')

# ── 02 · Votre peau a sa propre lumière — fils de soie, « lumière » qui naît du centre ──
fid = '02-lumiere'
F[fid] = ('', stage(bg=f'      <canvas class="X-cv" id="X-s" width="{W}" height="{H}"></canvas>\n', fg=dust(2, 8),
                    txt=words('Votre peau', 'X-d', 'top:690px; font-size:120px', 'X-l1') + words('a sa propre', 'X-d', 'top:820px; font-size:120px', 'X-l2') +
                        '    <div class="X-a X-c X-i st-glow X-gold" id="X-l3" style="top:960px; font-size:180px; color:%GOLD%">lumière.</div>\n'
                        '    <div class="X-line" id="X-ln" style="left:390px; top:1200px; width:300px"></div>\n'),
 drive(dur_of(fid), ['AURA.silk(R("#X-s"), { y: 980, spread: 520, n: 4, alpha: 0.13, seed: 12 })']) + dust_life(dur_of(fid)) +
 camera(fid, [{'t': 0, 's': 1.05, 'rx': 5, 'f': 1.0}, {'t': dur_of(fid), 's': 1.0, 'rx': 0, 'ease': 'breath'}], depths=(0.5, 1, 1.7, 0.8)) +
 '      tl.fromTo(R("#X-s"), { opacity: 0 }, { opacity: 1, duration: 1.6, ease: S.ease.breath }, 0);\n' +
 words_in('#X-l1', 0.3) + words_in('#X-l2', 0.95) + chars_in('#X-l3', 1.72, 1.8, 40, 22, 0.05) + line_in('#X-ln', 2.05, 1.4) +
 leave(['#X-l1', '#X-l2', '#X-l3', '#X-ln'], out_at(fid)) +
 f'      tl.to(R("#X-s"), {{ opacity: 0, duration: 0.8, ease: S.ease.accel }}, {out_at(fid)});\n')

# ── 03 · Soft Glow : mise au point de la poussière d'or vers le pot, push-in lent ──
fid = '03-softglow'
mh, mj = mist('X-m', {'x': 540, 'y': 1300, 'rise': 1200, 'size': 300, 'alpha': 0.075, 'n': 64, 'life': 6.5, 'sx': 800, 'fin': 0.3, 'seed': 21})
fh, fj, fo, fc = frame('X-f', 'softglow', 160, 200, 760, 1000, seed=22)
F[fid] = ('', stage(bg=mh + halo('X-h', 40, 120, 1000, 1100), mid=fh, fg=dust(3),
                    txt='''    <div class="X-a X-c X-i" id="X-n" style="top:1225px; font-size:150px">Soft Glow</div>
    <div class="X-a X-c X-cap" id="X-s1" style="top:1430px">Papaye · Niacinamide · Acide kojique</div>
''' + words('Une peau plus nette, plus lumineuse.', 'X-d', 'top:1490px; font-size:64px', 'X-s2')),
 drive(dur_of(fid), [mj, fj]) + dust_life(dur_of(fid)) +
 camera(fid, [{'t': 0, 's': 1.12, 'ry': -8, 'f': 1.7}, {'t': 2.2, 's': 1.0, 'ry': 0, 'f': 1.0}, {'t': dur_of(fid), 's': 1.05, 'ry': 2, 'ease': 'breath'}]) +
 breathe('#X-h', 0.4, dur_of(fid)) + morph_in('X-f', fc, fo, 0.1) +
 '      S.life(tl, [R("#X-f")], 1.6, ' + str(dur_of(fid)) + ', { y: 6, x: 2, rotate: 0.25, scale: 0.004, period: 6, seed: 31 });\n' +
 chars_in('#X-n', 0.75) + soft_in('#X-s1', 1.9) + words_in('#X-s2', 3.45, 1.4, 26, 12, 0.08) +
 '      S.sweep(tl, R("#X-fsh"), 2.6, { duration: 1.8 });\n' +
 morph_out('X-f', fc, out_at(fid)) + leave(['#X-n', '#X-s1', '#X-s2'], out_at(fid) - 0.05))

# ── 04 · Le meilleur de la nature : trois orbes sur ressort, pan latéral en parallaxe ──
fid = '04-nature'
ORBS = [('papaye', 'Papaye', 205, 900), ('carotte', 'Carotte', 540, 1060), ('curcuma', 'Curcuma', 875, 900)]
oh, oj = '', ''
for i, (img, lab, cx, cy) in enumerate(ORBS):
    oh += (f'      <div class="X-orbi" id="X-o{i}" style="left:{cx - 125}px; top:{cy - 125}px"><img src="assets/images/{img}.jpg" alt=""></div>\n')
    t0 = (0.33, 0.81, 1.5)[i]
    oj += (f'      S.pop(tl, R("#X-o{i}"), {t0}, {{ from: 0.3, response: 0.6, damping: 0.78 }});\n'
           f'      tl.fromTo(R("#X-o{i}"), {{ filter: "blur(16px)" }}, {{ filter: "blur(0px)", duration: 0.9, ease: S.ease.silk }}, {t0});\n'
           + soft_in(f'#X-ol{i}', t0 + 0.3, 1.2, 20, 12))
labels = ''.join(f'    <div class="X-a X-i" id="X-ol{i}" data-layout-allow-occlusion style="left:{cx - 200}px; width:400px; text-align:center; top:{cy + 150}px; font-size:64px">{lab}</div>\n' for i, (img, lab, cx, cy) in enumerate(ORBS))  # bord du cadre, sous la vignette : voulu
mh, mj = mist('X-m', {'x': 540, 'y': 2050, 'rise': 1550, 'size': 360, 'alpha': 0.08, 'n': 80, 'life': 7.0, 'sx': 1000, 'fin': 0.3, 'seed': 31})
F[fid] = ('''
    .X-orbi { position: absolute; width: 250px; height: 250px; border-radius: 50%; overflow: hidden;
      box-shadow: 0 0 0 2px rgba(212,175,55,0.75), 0 0 60px rgba(212,175,55,0.35), 0 0 140px rgba(212,175,55,0.15), 0 30px 60px rgba(0,0,0,0.5); }
    .X-orbi img { width: 100%; height: 100%; object-fit: cover; display: block; }
    #X-svg { position: absolute; left: 0; top: 0; }
''', stage(bg=mh, mid='''      <svg id="X-svg" width="1080" height="1920"><path id="X-arc" d="M 205 900 Q 540 1230 875 900" fill="none" stroke="%GOLD%" stroke-width="1.2" stroke-opacity="0.7"/></svg>
''' + oh, fg=dust(4, 10, (120, 600, 960, 1300)),
           txt=words('Le meilleur', 'X-d', 'top:340px; font-size:110px', 'X-h1') + words('de la nature', 'X-i', 'top:465px; font-size:140px; color:%GOLD%', 'X-h2') +
               labels + words('au service de votre éclat.', 'X-i', 'top:1520px; font-size:72px', 'X-h3')),
 drive(dur_of(fid), [mj]) + dust_life(dur_of(fid)) +
 camera(fid, [{'t': 0, 'x': 50, 's': 1.06, 'ry': -6, 'f': 1.0}, {'t': dur_of(fid), 'x': -50, 's': 1.0, 'ry': 6, 'ease': 'breath'}], depths=(0.35, 1, 1.8, 0.4)) +
 '      const A = R("#X-arc"), AL = A.getTotalLength();\n'
 '      tl.fromTo(A, { attr: { "stroke-dasharray": AL + " " + AL, "stroke-dashoffset": AL } }, { attr: { "stroke-dashoffset": 0 }, duration: 2.2, ease: S.ease.glide }, 0.5);\n' +
 oj + f'      S.life(tl, [R("#X-o0"), R("#X-o1"), R("#X-o2")], 2.2, {dur_of(fid)}, {{ y: 12, x: 3, rotate: 0.8, scale: 0.01, period: 4.5, seed: 9 }});\n' +
 words_in('#X-h1', 2.27) + chars_in('#X-h2', 2.85, 1.6, 36, 16, 0.035, 'start') + words_in('#X-h3', 3.43, 1.1, 24, 12, 0.07) +
 leave(['#X-h1', '#X-h2', '#X-o0', '#X-o1', '#X-o2', '#X-ol0', '#X-ol1', '#X-ol2', '#X-h3', '#X-svg'], out_at(fid)))

# ── 05 · Intense Glow Skin : la caméra arrive de la droite et bascule face au pot ──
fid = '05-intense'
mh, mj = mist('X-m', {'x': 540, 'y': 1200, 'rise': 1100, 'size': 280, 'alpha': 0.075, 'n': 64, 'life': 6.5, 'sx': 760, 'fin': 0.3, 'seed': 41})
fh, fj, fo, fc = frame('X-f', 'intense', 190, 180, 700, 900, radius=(44, 44, 44, 44), seed=42)
F[fid] = ('', stage(bg=mh + halo('X-h', 40, 80, 1000, 1100), mid=fh, fg=dust(5, 12, (190, 180, 890, 1450)),
                    txt=words('Intense Glow Skin', 'X-i', 'top:1110px; font-size:124px', 'X-n') +
                        '    <div class="X-a X-c X-d" id="X-s2" style="top:1270px; font-size:70px; color:%GOLD%">La version intense.</div>\n'
                        '    <div class="X-a X-c X-cap" id="X-s1" style="top:1385px">Carotte · Alpha-arbutine · Collagène</div>\n'),
 drive(dur_of(fid), [mj, fj]) + dust_life(dur_of(fid)) +
 camera(fid, [{'t': 0, 'x': -70, 's': 1.1, 'ry': 12, 'f': 1.75}, {'t': 2.0, 'x': 0, 's': 1.0, 'ry': 0, 'f': 1.0}, {'t': dur_of(fid), 's': 1.05, 'ry': -3, 'ease': 'breath'}]) +
 breathe('#X-h', 0.4, dur_of(fid)) + morph_in('X-f', fc, fo, 0.1) +
 f'      S.life(tl, [R("#X-f")], 1.6, {dur_of(fid)}, {{ y: 6, x: 2, rotate: 0.25, scale: 0.004, period: 6, seed: 33 }});\n' +
 words_in('#X-n', 0.65, 1.6, 40, 16, 0.12) + chars_in('#X-s2', 1.85, 1.4, 28, 12, 0.025, 'start') + soft_in('#X-s1', 2.6) +
 '      S.sweep(tl, R("#X-fsh"), 2.8, { duration: 1.8 });\n' +
 morph_out('X-f', fc, out_at(fid)) + leave(['#X-n', '#X-s1', '#X-s2'], out_at(fid) - 0.05))

# ── 06 · Le rituel visage : chaque soin sur son verbe, grue descendante ──
fid = '06-visage'
TRIO = [('nila', 'Nettoyer', 'Savon Nila', 0.4), ('perfectskin', 'Réparer', 'Perfect Skin', 1.09), ('hydra', 'Hydrater', 'Hydra Face Cream', 1.78)]
th, ttx, tjs, tm = '', '', '', []
for i, (img, step, prod, t0) in enumerate(TRIO):
    x = 40 + i * 340
    h_, j_, o_, c_ = frame(f'X-f{i}', img, x, 520, 320, 520, radius=(160, 160, 22, 22), vap={'size': 110, 'n': 34, 'alpha': 0.13}, seed=50 + i)
    th += h_
    ttx += (f'    <div class="X-a X-i" id="X-n{i}" style="left:{x}px; width:320px; text-align:center; top:1060px; font-size:66px">{step}</div>\n'
            f'    <div class="X-a X-cap" id="X-s{i}" style="left:{x}px; width:320px; text-align:center; top:1150px; font-size:18px; letter-spacing:0.24em">{prod}</div>\n')
    tm.append(j_)
    tjs += (f'      tl.fromTo(R("#X-f{i}"), {{ opacity: 0, y: 80, filter: "blur(16px)", clipPath: "{c_}" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", clipPath: "{o_}", duration: 1.5, ease: S.ease.silk }}, {t0:.2f});\n'
            f'      tl.fromTo(R("#X-f{i}i"), {{ scale: 1.2 }}, {{ scale: 1.0, duration: 4.5, ease: "power2.out" }}, {t0:.2f});\n'
            + chars_in(f'#X-n{i}', t0 + 0.2, 1.3, 28, 12, 0.03, 'start') + soft_in(f'#X-s{i}', t0 + 0.5, 1.0, 12, 6))
F[fid] = ('', stage(mid=th, fg=dust(6, 10, (20, 470, 1060, 1250)),
           txt=words('Le rituel visage', 'X-i', 'top:300px; font-size:110px', 'X-t') + ttx +
               words('Plus nette. Plus lumineuse.', 'X-d', 'top:1300px; font-size:72px', 'X-cl') + '    <div class="X-line" id="X-ln" style="left:390px; top:1430px; width:300px"></div>\n'),
 drive(dur_of(fid), tm) + dust_life(dur_of(fid)) +
 camera(fid, [{'t': 0, 'y': -70, 's': 1.08, 'rx': -6, 'f': 1.0}, {'t': dur_of(fid), 'y': 10, 's': 1.0, 'rx': 0, 'ease': 'breath'}]) +
 tjs + f'      S.life(tl, [R("#X-f0"), R("#X-f1"), R("#X-f2")], 2.0, {dur_of(fid)}, {{ y: 6, rotate: 0.3, scale: 0.004, period: 5, seed: 17 }});\n' +
 '      S.sweep(tl, [R("#X-f0sh"), R("#X-f1sh"), R("#X-f2sh")], 3.0, { duration: 1.6 });\n' +
 chars_in('#X-t', 2.55, 1.5, 34, 16, 0.035, 'start') + words_in('#X-cl', 3.3, 1.2, 24, 12, 0.09) + line_in('#X-ln', 3.6, 1.1) +
 leave(['#X-t', '#X-f0', '#X-f1', '#X-f2', '#X-n0', '#X-n1', '#X-n2', '#X-s0', '#X-s1', '#X-s2', '#X-cl', '#X-ln'], out_at(fid)))

# ── 07 · Bridal Glow Ritual : grand push-in, mise au point sur le coffret ──
fid = '07-bridal'
mh, mj = mist('X-m', {'x': 540, 'y': 1450, 'rise': 1350, 'size': 320, 'alpha': 0.075, 'n': 64, 'life': 6.5, 'sx': 900, 'fin': 0.3, 'seed': 61})
fh, fj, fo, fc = frame('X-f', 'bridal', 110, 260, 860, 1020, radius=(430, 430, 40, 40), seed=62)
F[fid] = ('', stage(bg=mh + halo('X-h', 0, 160, 1080, 1200), mid=fh, fg=dust(7, 10, (110, 260, 970, 1600)),
                    txt=words('Bridal Glow Ritual', 'X-i', 'top:1290px; font-size:116px', 'X-n') +
                        words('Le rituel des grands jours.', 'X-d', 'top:1430px; font-size:66px', 'X-s2') +
                        '    <div class="X-a X-c X-cap" id="X-s1" style="top:1540px">Visage &amp; corps · 4 soins</div>\n'),
 drive(dur_of(fid), [mj, fj]) + dust_life(dur_of(fid)) +
 camera(fid, [{'t': 0, 's': 0.96, 'f': 1.7}, {'t': 1.8, 's': 1.0, 'f': 1.0}, {'t': dur_of(fid), 's': 1.07, 'ease': 'breath'}]) +
 breathe('#X-h', 0.3, dur_of(fid)) + morph_in('X-f', fc, fo, 0.1, 1.6) +
 f'      S.life(tl, [R("#X-f")], 1.4, {dur_of(fid)}, {{ y: 5, rotate: 0.2, scale: 0.004, period: 6, seed: 35 }});\n' +
 words_in('#X-n', 0.55, 1.6, 40, 16, 0.12) + words_in('#X-s2', 1.75, 1.3, 26, 12, 0.08) + soft_in('#X-s1', 2.3) +
 '      S.sweep(tl, R("#X-fsh"), 2.0, { duration: 1.8 });\n' +
 morph_out('X-f', fc, out_at(fid)) + leave(['#X-n', '#X-s1', '#X-s2'], out_at(fid) - 0.05))

# ── 08 · signature : léger recul de caméra, lueur dorée sur la promesse ──
fid = '08-logo'
mh, mj = mist('X-v', {'x': 540, 'y': 2050, 'rise': 1500, 'size': 360, 'alpha': 0.085, 'n': 80, 'life': 7.0, 'sx': 1000, 'fin': 0.3, 'seed': 9})
F[fid] = ('', stage(bg=mh + halo('X-orb', 90, 380, 900, 700), fg=dust(8, 10, (60, 450, 1020, 1300)),
                    txt=wordmark('X-nm', 560, 190) + '''    <div class="X-a X-c X-cap" id="X-p" style="top:780px; font-size:30px; letter-spacing:0.9em; padding-left:0.9em">Paris</div>
    <div class="X-a X-c X-i st-glow X-gold" id="X-t" style="top:930px; font-size:96px; color:%GOLD%">Révélez votre éclat.</div>
    <div class="X-line" id="X-ln" style="left:390px; top:1090px; width:300px"></div>
    <div class="X-a X-c X-cap" id="X-w" style="top:1140px; color:%CHAMP%; font-size:34px; letter-spacing:0.16em; text-transform:none">nessaparisbeauty.com</div>
    <div class="X-a X-c X-cap" id="X-k" style="top:1215px; font-size:24px">Soins visage &amp; corps</div>
'''),
 drive(dur_of(fid), [mj]) + dust_life(dur_of(fid)) +
 camera(fid, [{'t': 0, 's': 1.08, 'f': 1.0}, {'t': dur_of(fid), 's': 1.0, 'ease': 'silk'}], depths=(0.4, 1, 1.7, 0.7)) +
 '      tl.fromTo(R("#X-orb"), { scale: 0.2, opacity: 0 }, { scale: 1, opacity: 1, duration: 1.8, ease: S.ease.silk }, 0.0);\n' +
 wordmark_in('X-nm', 0.1, 50) + soft_in('#X-p', 0.75, 1.2, 0, 6) + words_in('#X-t', 1.07, 1.5, 30, 16, 0.12).replace('RA("#X-t .X-w")', 'S.split(R("#X-t"), { by: "words" })') +
 line_in('#X-ln', 1.45, 1.2) + soft_in('#X-w', 1.75) + soft_in('#X-k', 2.0))

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
      const S = STUDIO;
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
        trans += f'        tl.fromTo("#el-{fid}", {{ opacity: 0 }}, {{ opacity: 1, duration: {OV}, ease: STUDIO.ease.breath }}, {st});\n'
breaths = ''.join(f'      <audio id="br{i}" src="assets/breath.wav" data-start="{round(st - 0.3, 2)}" data-duration="1.1" data-track-index="{12 + i % 3}" data-volume="0.18"></audio>\n' for i, (fid, st, ln) in enumerate(SC) if st > 0)
VOJ = f'{P}/assets/voice/voice.json'
voice = os.path.exists(VOJ)
vo = ''.join(f'      <audio id="vo{i}" src="{s}" data-start="{a}" data-duration="{d}" data-track-index="{30 + i}" data-volume="1"></audio>\n' for i, (s, a, d) in enumerate(json.load(open(VOJ)))) if voice else ''
MB = open(f'{P}/compositions/components/motion-blur.html').read()
idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/aura.js"></script>
    <script src="assets/vendor/studio.js"></script>
    <link rel="stylesheet" href="assets/vendor/studio.css" />
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #08080C; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #08080C; }}
      .scene {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
      #bg {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
      #vig {{ position: absolute; left: 0; top: 0; pointer-events: none; }}
      #grain {{ opacity: 0.06; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
      <canvas id="bg" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" width="{W}" height="{H}"></canvas>
{scenes}      <canvas id="grain" class="clip st-grain" data-start="0" data-duration="{TOTAL}" data-track-index="8" width="{W}" height="{H}"></canvas>
      <canvas id="vig" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="9" width="{W}" height="{H}"></canvas>
      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="11" data-volume="{0.24 if voice else 0.85}"></audio>
{breaths}{vo}    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
      (function () {{ var tl = window.__timelines["main"];
        var bg = AURA.backdrop(document.getElementById("bg"), {{ seed: 17, dust: 160 }});
        var p = {{ t: 0 }};
        tl.fromTo(p, {{ t: 0 }}, {{ t: {TOTAL}, duration: {TOTAL}, ease: "none", onUpdate: function () {{ bg(p.t, Math.min(1, p.t / 1.5 + 0.25)); }} }}, 0);
        bg(0, 0.25);
        (function (c) {{ var g = c.getContext("2d"), r = g.createRadialGradient(540, 864, 0, 540, 864, 1150);
          r.addColorStop(0, "rgba(8,8,12,0)"); r.addColorStop(0.55, "rgba(8,8,12,0)"); r.addColorStop(1, "rgba(8,8,12,0.72)");
          g.fillStyle = r; g.fillRect(0, 0, {W}, {H}); }})(document.getElementById("vig"));
        STUDIO.drive(tl, 0, {TOTAL}, [STUDIO.grain(document.getElementById("grain"), {{ fps: 25, seed: 7 }})]);
{trans}        tl.to({{}}, {{ duration: {TOTAL} }}, 0);
      }})();
    </script>
{MB}
  </body>
</html>
'''
open(f'{P}/index.html', 'w').write(idx)
print('ok', TOTAL)
