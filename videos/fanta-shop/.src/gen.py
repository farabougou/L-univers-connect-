# Fanta shop (@fantafofana61) : pub verticale de 24 s, 100 BPM (1 temps = 0,6 s), coupes sur les temps.
# Histoire : une maison qui sent bon → le woussoulan « Chez Mme Traoré » se pose sur son plateau tressé → rouge ou doré
# → aussi en flacon spray → savons et foulards → le numéro de la boutique.
# Rien d'inventé : seuls les mots des étiquettes (Woussoulan Soumadouman, Chez Mme Traoré), de la page TikTok
# (Fanta shop, 77 22 42 50, Fanta savon) et ce qui se voit sur les photos (pots rouges et dorés, flacon spray, foulards).
# Les chiffres du numéro défilent sur des bandes masquées : les chiffres cachés sont marqués allow-occlusion/overflow.
# Signature visuelle : le plateau tressé bleu et paille des vidéos de la boutique. Ses anneaux tournent et se calent,
# et chaque transition est un cercle qui s'ouvre depuis lui. Musique : score.py ; photos : prep.py.
import os, re
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS, TOTAL = 1080, 1920, 60, 24.0
INK, WINE, RED, GOLD, CREAM, SAND, BLUE = '#1A0806', '#4A0D08', '#C8261A', '#E8B04B', '#F6EAD7', '#F1E2C6', '#2F6BD0'

def words(line):
    # un mot = un masque ; un passage <em> garde sa couleur mot par mot
    out = []
    for tok in re.findall(r'<em[^>]*>.*?</em>|[^<\s]+', line):
        m = re.match(r'(<em[^>]*>)(.*?)</em>', tok)
        out += [f'{m.group(1)}{w}</em>' for w in m.group(2).split()] if m else [tok]
    return ' '.join(f'<span class=st-mask><span class=st-word>{w}</span></span>' for w in out)

def chars(text, cls=''):
    return ''.join(' ' if c == ' ' else f'<span class="st-char {cls}">{c}</span>' for c in text)

def tray(uid, size, flat=1.0, n=13, R=480, r0=70, straw='#E8D6B0', stitch='#9C7A48', blue=BLUE, gap='#6E4E2A', rim=2):
    # plateau tressé : anneaux de paille cousus, secteurs bleus en triangles, bord bleu ; chaque anneau tourne seul
    sp = (R - r0) / n; sw = sp * 0.94; rings = ''
    for k in range(n):
        rk = r0 + sp * (k + 0.5)
        g = f'<circle r="{rk:.1f}" fill="none" stroke="{straw}" stroke-width="{sw:.1f}"/>'
        if k >= n - rim: g += f'<circle r="{rk:.1f}" fill="none" stroke="{blue}" stroke-width="{sw:.1f}"/>'
        elif k >= 2:
            wk = 4 + 44 * (1 - (k - 2) / (n - rim - 3))
            if wk > 4.5: g += f'<circle r="{rk:.1f}" fill="none" stroke="{blue}" stroke-width="{sw:.1f}" pathLength="360" stroke-dasharray="{wk:.1f} {60 - wk:.1f}" stroke-dashoffset="{wk / 2:.1f}"/>'
        g += f'<circle r="{rk:.1f}" fill="none" stroke="{stitch}" stroke-width="{sw:.1f}" stroke-dasharray="1.6 6.4" opacity="0.55"/>'
        g += f'<circle r="{rk + sp / 2:.1f}" fill="none" stroke="{gap}" stroke-width="1.6" opacity="0.5"/>'
        rings += f'<g class="rg" id="{uid}r{k}">{g}</g>'
    core = f'<circle r="{r0:.0f}" fill="{straw}"/><circle r="{r0 * 0.6:.0f}" fill="none" stroke="{stitch}" stroke-width="{r0 * 0.8:.0f}" stroke-dasharray="1.6 6" opacity="0.5"/>'
    return (f'<svg class="tray" id="{uid}" viewBox="-500 -500 1000 1000" width="{size}" height="{size}">'
            f'<g transform="scale(1 {flat})"><g id="{uid}s">{core}{rings}</g></g></svg>')

HEXES = [('t-rouge', 70, 446), ('t-plateau', 570, 446), ('t-dore', 320, 839)]   # (photo, gauche, haut) en nid d'abeille
NUM = '77 22 42 50'

S1 = f'''
          <div class="cam" id="cam1"><img class="bgimg" src="assets/photos/bg-rouge.jpg" alt="" /></div>
          <div class="shade"></div>
          <div class="txt" id="h1"><div class="kick" id="k1">FANTA SHOP</div>
            <div class="hd">{words("Ta maison")}</div><div class="hd">{words("va sentir")}</div>
            <div class="hd" id="bon">{chars("bon.", "gold")}</div></div>'''
S2 = f'''
          <div class="st-stage">
            <div class="st-layer" id="l2bg"><img class="bgimg" src="assets/photos/bg-dore.jpg" alt="" /><div class="shade warm"></div><div class="glow" id="glow2"></div></div>
            <div class="st-layer" id="l2tray"><div id="wA">{tray("tA", 980, flat=0.34)}</div></div>
            <div class="st-layer" id="l2jar"><div id="jar2" class="jarw"><div class="jsh"></div><img src="assets/photos/pots.png" alt="" />
              <div class="jsheen st-sheen-host"><i class="st-sheen" id="sh2"></i></div></div></div>
            <div class="st-layer" id="l2txt"><div class="txt" id="h2"><div class="title" id="wou">{chars("Woussoulan")}</div>
              <div class="sub" id="sou">{chars("Soumadouman")}</div><div class="kick" id="k2">CHEZ MME TRAORÉ</div></div></div>
          </div>'''
S3 = f'''
          <div class="cam" id="cam3">
            <div id="wB">{tray("tB", 1500, straw="#EAD9B9", stitch="#C9A878", blue="#D9583F", gap="#C9A878", rim=1)}</div>
            <div class="txt dark" id="h3"><div class="hd sm">{words("Rouge ou doré,")}</div><div class="hd sm">{words("à toi de <em>choisir.</em>")}</div></div>
            {"".join(f'<div class="hexw" id="hx{i}" style="left:{x}px; top:{y}px"><div class="hex"><div class="hexin"><img src="assets/photos/{p}.jpg" alt="" /></div></div></div>' for i, (p, x, y) in enumerate(HEXES))}
            <div class="kick dark" id="k3">WOUSSOULAN · SOUMADOUMAN</div>
          </div>'''
S4 = f'''
          <div class="cam" id="cam4"><img class="bgimg" src="assets/photos/bg-rouge.jpg" alt="" /></div>
          <div class="shade red"></div>
          <div id="fl"><div id="flin"><img src="assets/photos/flacon.jpg" alt="" /></div></div>
          <canvas id="mist" width="{W}" height="{H}"></canvas>
          <div class="txt" id="h4"><div class="hd sm">{words("Aussi en")}</div><div class="hd sm">{words("<em>flacon spray.</em>")}</div></div>'''
S5 = f'''
          <div class="cam" id="cam5">
            <div class="txt dark" id="h5"><div class="hd sm">{words("Et ce n’est")}</div><div class="hd sm">{words("pas <em>tout.</em>")}</div></div>
            <div class="pol" id="pA"><div class="pimg"><img src="assets/photos/savon.jpg" alt="" /></div><div class="pcap" id="cA">Savons</div></div>
            <div class="pol" id="pB"><div class="pimg"><img src="assets/photos/foulards.jpg" alt="" /></div><div class="pcap" id="cB">Foulards</div></div>
          </div>'''
digits = ''.join('<span class="gap"></span>' if c == ' ' else
                 f'<span class="dg"><span class="strip" data-layout-allow-overflow data-d="{c}">{"".join(f"<b data-layout-allow-occlusion data-layout-allow-overflow>{d % 10}</b>" for d in range(20))}</span></span>' for c in NUM)
S6 = f'''
          <div class="cam" id="cam6"><div id="wC">{tray("tC", 1700, straw="#F3C76E", stitch="#7A1A0E", blue="#F6EAD7", gap="#7A1A0E", rim=1)}</div><div class="glow" id="glow6"></div></div>
          <div class="kick" id="k6">WOUSSOULAN · SAVONS · FOULARDS</div>
          <div id="brand">{chars("Fanta")} {chars("shop", "gold it")}</div>
          <div id="jar6" class="jarw"><div class="jsh"></div><img src="assets/photos/pots.png" alt="" /></div>
          <div class="kick" id="k7">COMMANDE AU +223</div>
          <div id="num" class="st-sheen-host">{digits}<i class="st-sheen" id="sh6"></i></div>
          <div id="handle">@fantafofana61</div>'''

HTML = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/studio.js"></script>
    <link rel="stylesheet" href="assets/vendor/studio.css" />
    <style>
      @font-face {{ font-family: "Instrument Serif"; font-style: normal; src: url("assets/fonts/instrument-serif-latin-400-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Instrument Serif"; font-style: italic; src: url("assets/fonts/instrument-serif-latin-400-italic.woff2") format("woff2"); }}
      @font-face {{ font-family: "Montserrat"; font-weight: 500; src: url("assets/fonts/montserrat-latin-500-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Montserrat"; font-weight: 600; src: url("assets/fonts/montserrat-latin-600-normal.woff2") format("woff2"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {INK}; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {INK}; color: {CREAM}; font-family: "Montserrat", sans-serif; }}
      .sc {{ position: absolute; inset: 0; visibility: hidden; overflow: hidden; }}
      .cam {{ position: absolute; inset: 0; transform-origin: 540px 900px; }}
      .bgimg {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; }}
      .shade {{ position: absolute; inset: 0; background: radial-gradient(ellipse 80% 60% at 50% 45%, rgba(26,8,6,0.35), rgba(26,8,6,0.88) 100%); }}
      .shade.warm {{ background: radial-gradient(ellipse 70% 50% at 50% 62%, rgba(74,13,8,0.25), rgba(26,8,6,0.9) 100%); }}
      .shade.red {{ background: radial-gradient(ellipse 80% 60% at 50% 50%, rgba(140,24,14,0.55), rgba(26,8,6,0.92) 100%); }}
      .glow {{ position: absolute; border-radius: 50%; background: radial-gradient(circle, rgba(232,176,75,0.42), rgba(232,176,75,0.12) 45%, rgba(232,176,75,0) 70%); }}
      /* textes */
      .txt {{ position: absolute; left: 70px; right: 70px; text-align: center; }}
      .kick {{ font: 600 26px "Montserrat"; letter-spacing: 0.32em; color: {GOLD}; white-space: nowrap; }}
      .kick.dark {{ color: {RED}; }}
      .hd {{ font: 400 150px/1.02 "Instrument Serif"; letter-spacing: -0.015em; color: {CREAM}; white-space: nowrap; text-shadow: 0 6px 40px rgba(0,0,0,0.45); }}
      .hd.sm {{ font-size: 124px; }}
      .hd em, .gold {{ font-style: italic; color: {GOLD}; }}
      .dark .hd {{ color: {INK}; text-shadow: none; }} .dark .hd em {{ color: {RED}; }}
      #h1 {{ top: 600px; }} #k1 {{ margin-bottom: 30px; }}
      #bon {{ font-size: 300px; line-height: 0.95; --st-glow: rgba(232,176,75,0.55); }}
      #bon .st-char {{ text-shadow: 0 0 2px rgba(255,255,255,0.3), 0 0 26px rgba(232,176,75,0.55), 0 0 80px rgba(232,176,75,0.35); }}
      /* le pot sur son plateau */
      #glow2 {{ left: -60px; top: 620px; width: 1200px; height: 1200px; }}
      #wA {{ position: absolute; left: 50px; top: 1050px; }}
      .jarw {{ position: absolute; }}
      .jarw img {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; filter: drop-shadow(0 0 1px rgba(255,220,170,0.5)); }}
      .jsh {{ position: absolute; left: -20%; right: -20%; bottom: -5%; height: 14%; border-radius: 50%; background: radial-gradient(ellipse, rgba(20,6,4,0.7), rgba(20,6,4,0) 70%); }}
      #jar2 {{ left: 340px; top: 645px; width: 400px; height: 909px; }}
      .jsheen {{ position: absolute; inset: 0; -webkit-mask-image: url("assets/photos/pots.png"); mask-image: url("assets/photos/pots.png"); -webkit-mask-size: 100% 100%; mask-size: 100% 100%; }}
      #h2 {{ top: 196px; }}
      .title {{ font: 400 176px/1 "Instrument Serif"; color: {CREAM}; white-space: nowrap; text-shadow: 0 6px 40px rgba(0,0,0,0.5); }}
      .sub {{ font: italic 400 104px/1.05 "Instrument Serif"; color: {GOLD}; white-space: nowrap; margin-top: 2px; }}
      #k2 {{ margin-top: 18px; color: {CREAM}; opacity: 0.85; }}
      /* la gamme */
      #s3, #s5 {{ background: radial-gradient(ellipse 90% 70% at 50% 45%, #FBF3E4, {SAND} 70%, #E6D2AE 100%); }}
      #wB {{ position: absolute; left: -210px; top: 260px; opacity: 0.3; }}
      #h3 {{ top: 196px; }}
      .hexw {{ position: absolute; width: 440px; height: 508px; filter: drop-shadow(0 4px 6px rgba(74,13,8,0.25)) drop-shadow(0 22px 34px rgba(74,13,8,0.3)); }}
      .hex {{ position: absolute; inset: 0; clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%); background: linear-gradient(160deg, #F6D58A, {GOLD} 45%, #A8742A); }}
      .hexin {{ position: absolute; inset: 10px; clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%); overflow: hidden; }}
      .hexin img {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
      #k3 {{ position: absolute; left: 0; right: 0; top: 1390px; text-align: center; }}
      /* le flacon */
      #fl {{ position: absolute; left: 280px; top: 560px; width: 520px; height: 839px; padding: 10px; border-radius: 260px 260px 36px 36px;
             background: linear-gradient(160deg, #F6D58A, {GOLD} 45%, #A8742A); box-shadow: 0 3px 6px rgba(0,0,0,0.3), 0 24px 50px rgba(0,0,0,0.45), 0 70px 140px rgba(0,0,0,0.5); }}
      #flin {{ position: relative; width: 100%; height: 100%; border-radius: 250px 250px 28px 28px; overflow: hidden; }}
      #flin img {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
      #mist {{ position: absolute; left: 0; top: 0; opacity: 0.5; mix-blend-mode: screen; }}
      #h4 {{ top: 196px; }}
      /* la boutique */
      #h5 {{ top: 196px; }}
      .pol {{ position: absolute; width: 440px; padding: 14px 14px 0; background: #FCF7EE; box-shadow: 0 2px 4px rgba(74,13,8,0.2), 0 18px 36px rgba(74,13,8,0.25), 0 50px 90px rgba(74,13,8,0.25); }}
      .pimg {{ position: relative; width: 412px; height: 564px; overflow: hidden; }}
      .pimg img {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
      .pcap {{ height: 96px; display: flex; align-items: center; justify-content: center; font: italic 400 66px "Instrument Serif"; color: {RED}; }}
      #pA {{ left: 70px; top: 560px; }} #pB {{ left: 560px; top: 640px; }}
      /* l'appel */
      #s6 {{ background: radial-gradient(ellipse 85% 65% at 50% 45%, #B3211A, #6A0F0A 62%, #2A0806 100%); }}
      #wC {{ position: absolute; left: -310px; top: 70px; opacity: 0.07; }}
      #glow6 {{ left: 90px; top: 380px; width: 900px; height: 900px; }}
      #k6 {{ position: absolute; left: 0; right: 0; top: 214px; text-align: center; font-size: 22px; color: {CREAM}; opacity: 0.9; }}
      #brand {{ position: absolute; left: 0; right: 0; top: 262px; text-align: center; font: 400 178px/1 "Instrument Serif"; color: {CREAM}; white-space: nowrap; text-shadow: 0 6px 40px rgba(0,0,0,0.4); }}
      #jar6 {{ left: 420px; top: 500px; width: 240px; height: 545px; }}
      #k7 {{ position: absolute; left: 0; right: 0; top: 1124px; text-align: center; }}
      #num {{ position: absolute; left: 0; right: 0; margin: 0 auto; width: fit-content; top: 1170px; display: flex; font: 600 128px/1 "Montserrat"; color: {CREAM}; white-space: nowrap; padding: 6px 10px; }}
      .dg {{ display: inline-block; width: 0.66em; height: 1em; overflow: hidden; }}
      .strip {{ display: block; }} .strip b {{ display: block; height: 1em; text-align: center; font-weight: 600; }}
      .gap {{ display: inline-block; width: 0.3em; }}
      #handle {{ position: absolute; left: 0; right: 0; margin: 0 auto; width: fit-content; top: 1352px; padding: 20px 46px; border-radius: 60px; border: 2.5px solid {GOLD};
                 font: 600 44px "Montserrat"; color: {GOLD}; white-space: nowrap; background: rgba(26,8,6,0.25); }}
      /* transitions et finitions */
      .ring {{ position: absolute; opacity: 0; border-radius: 50%; border: 8px solid {GOLD}; pointer-events: none; }}
      #smoke {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; opacity: 0.5; mix-blend-mode: screen; pointer-events: none; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
      <div id="frame" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0">
        <div class="sc" id="s1">{S1}
        </div>
        <div class="sc" id="s2">{S2}
        </div>
        <div class="sc" id="s3">{S3}
        </div>
        <div class="sc" id="s4">{S4}
        </div>
        <div class="sc" id="s5">{S5}
        </div>
        <div class="sc" id="s6">{S6}
        </div>
        <div class="ring" id="rA" data-layout-allow-overflow style="left:{540 - 1240}px; top:{1100 - 1240}px; width:2480px; height:2480px"></div>
        <div class="ring" id="rB" data-layout-allow-overflow style="left:{540 - 1650}px; top:{1540 - 1650}px; width:3300px; height:3300px; border-color:{RED}"></div>
        <div class="ring" id="rC" data-layout-allow-overflow style="left:{540 - 1110}px; top:{960 - 1110}px; width:2220px; height:2220px"></div>
        <canvas id="smoke" width="540" height="960"></canvas>
        <div class="st-vignette"></div>
        <canvas id="grain" class="st-grain" width="{W}" height="{H}" style="opacity:0.07"></canvas>
      </div>
      <audio id="music" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="10" data-volume="1"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      (function () {{
        const S = STUDIO, $ = (q) => document.querySelector(q), $$ = (q) => Array.from(document.querySelectorAll(q));
        const tl = gsap.timeline({{ paused: true }}), cl = (x) => Math.min(1, Math.max(0, x)), once = {{ immediateRender: false }};
        const TOTAL = {TOTAL};
%%JS%%
        tl.to({{}}, {{ duration: TOTAL }}, 0);
        window.__timelines["main"] = tl;
      }})();
    </script>
  </body>
</html>
'''
JS = r'''
        // ── plans : chaque scène est visible pendant sa transition d'entrée et de sortie ──
        [["#s1", 0, 3.4], ["#s2", 2.75, 7.25], ["#s3", 6.7, 11.75], ["#s4", 11.1, 14.45], ["#s5", 13.95, 18.05], ["#s6", 17.5, TOTAL]].forEach(([id, a, b]) => {
          tl.set(id, { visibility: "visible" }, a); if (b < TOTAL) tl.set(id, { visibility: "hidden" }, b);
        });
        // transition « plateau » : un cercle s'ouvre depuis un centre, un anneau de couleur court sur son bord
        const iris = (scene, ring, x, y, R, at, d) => {
          tl.fromTo(scene, { clipPath: `circle(0px at ${x}px ${y}px)` }, { clipPath: `circle(${R}px at ${x}px ${y}px)`, duration: d, ease: S.ease.swift }, at);
          tl.set(ring, { opacity: 1 }, at);
          tl.fromTo(ring, { scale: 0 }, { scale: 1, duration: d, ease: S.ease.swift }, at);
          tl.fromTo(ring, { opacity: 1 }, { opacity: 0, duration: d * 0.5, ease: S.ease.accel, ...once }, at + d * 0.5);
          tl.set(scene, { clipPath: "none" }, at + d);
        };

        // ── 1. l'accroche (0 → 3,0) ──
        tl.fromTo("#s1", { opacity: 0 }, { opacity: 1, duration: 0.5, ease: S.ease.silk }, 0);
        tl.fromTo("#cam1", { scale: 1.14 }, { scale: 1.0, duration: 3.4, ease: S.ease.glide }, 0);
        S.rise(tl, "#k1", 0.15, { y: 14, blur: 6, duration: 0.6 });
        S.maskUp(tl, $$("#h1 .hd:nth-child(2) .st-word"), 0.3, { duration: 0.7 });
        S.maskUp(tl, $$("#h1 .hd:nth-child(3) .st-word"), 0.75, { duration: 0.7 });
        S.converge(tl, $$("#bon .st-char"), 1.3, { spread: 70, duration: 0.9, stagger: 0.05 });
        S.leave(tl, ["#k1", ...$$("#h1 .hd")], 2.5, { y: -40, blur: 10, duration: 0.4, stagger: 0.04 });

        // ── 2. le pot sur son plateau (3,0 → 7,2) ──
        iris("#s2", "#rA", 540, 1100, 1240, 2.75, 0.5);
        S.camera(tl, [{ el: $("#l2bg"), depth: 0.35 }, { el: $("#l2tray"), depth: 0.8 }, { el: $("#l2jar"), depth: 1 }, { el: $("#l2txt"), depth: 1.15, blur: false }],
          { start: 2.75, end: 7.25, keys: [{ t: 2.75, s: 1.0, y: 0 }, { t: 7.25, s: 1.07, y: -24 }], drift: { x: 4, y: 3, r: 0.1, period: 8 } });
        const js = S.spring({ response: 0.55, damping: 0.78 });
        tl.fromTo("#jar2", { y: -1250, rotation: -6 }, { y: 0, rotation: 0, duration: js.duration, ease: js.ease }, 2.9);
        tl.fromTo("#jar2 .jsh", { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.5, ease: S.ease.silk }, 3.0);
        tl.fromTo("#glow2", { opacity: 0, scale: 0.7 }, { opacity: 1, scale: 1, duration: 1.2, ease: S.ease.silk }, 3.0);
        S.converge(tl, $$("#wou .st-char"), 3.3, { spread: 34, duration: 0.9, stagger: 0.035 });
        S.rise(tl, $$("#sou .st-char"), 3.75, { y: 30, blur: 8, duration: 0.8, stagger: 0.03 });
        S.rise(tl, "#k2", 4.25, { y: 12, blur: 6, duration: 0.6 });
        S.life(tl, $("#jar2 img"), 4.2, 7.3, { y: 5, x: 2, rotate: 0.4, period: 4, seed: 5 });
        S.sweep(tl, "#sh2", 5.0, { duration: 1.3 });
        S.leave(tl, ["#wou", "#sou", "#k2"], 6.45, { y: -30, blur: 8, duration: 0.3, stagger: 0.04 });

        // ── 3. rouge ou doré (7,2 → 11,4) : le crème s'ouvre depuis le plateau, trois tuiles sur les temps ──
        iris("#s3", "#rB", 540, 1540, 1650, 6.7, 0.5);
        tl.fromTo("#cam3", { scale: 1.0 }, { scale: 1.05, duration: 4.1, ease: S.ease.glide }, 7.0);
        S.maskUp(tl, $$("#h3 .hd:nth-child(1) .st-word"), 7.3, { duration: 0.7 });
        S.maskUp(tl, $$("#h3 .hd:nth-child(2) .st-word"), 7.6, { duration: 0.7 });
        const hs = S.spring({ response: 0.5, damping: 0.74 });
        [7.2, 7.8, 8.4].forEach((t, i) => {
          tl.fromTo("#hx" + i, { opacity: 0, scale: 0.55, rotation: i === 1 ? 10 : -10, y: 60 }, { opacity: 1, scale: 1, rotation: 0, y: 0, duration: hs.duration, ease: hs.ease }, t);
          tl.fromTo("#hx" + i + " img", { scale: 1.2 }, { scale: 1.0, duration: 11.75 - t, ease: S.ease.glide }, t);
        });
        S.life(tl, $$(".hexw"), 8.6, 11.8, { y: 7, x: 3, rotate: 0.5, period: 4.5, seed: 11 });
        S.rise(tl, "#k3", 8.9, { y: 12, blur: 6, duration: 0.6 });

        // ── 4. le flacon (11,4 → 14,4) : traversée, puis un nuage de spray sur le temps ──
        S.pushThrough(tl, "#s3", "#s4", 11.1, { duration: 0.6, outScale: 1.3, inScale: 0.88 });
        tl.fromTo("#cam4", { scale: 1.1 }, { scale: 1.0, duration: 3.4, ease: S.ease.glide }, 11.1);
        const fs = S.spring({ response: 0.6, damping: 0.8 });
        tl.fromTo("#fl", { y: 160, rotation: 3 }, { y: 0, rotation: 0, duration: fs.duration, ease: fs.ease }, 11.25);
        tl.fromTo("#flin img", { scale: 1.12 }, { scale: 1.0, duration: 3.3, ease: S.ease.glide }, 11.2);
        S.maskUp(tl, $$("#h4 .hd:nth-child(1) .st-word"), 11.5, { duration: 0.7 });
        S.maskUp(tl, $$("#h4 .hd:nth-child(2) .st-word"), 11.8, { duration: 0.7 });
        tl.fromTo("#fl", { scale: 1 }, { scale: 1.025, duration: 0.08, ease: S.ease.swift, immediateRender: false }, 12.0);
        tl.fromTo("#fl", { scale: 1.025 }, { scale: 1, duration: 0.5, ease: S.ease.silk, immediateRender: false }, 12.08);
        S.life(tl, $("#flin"), 12.2, 14.5, { y: 4, x: 2, rotate: 0.3, period: 4, seed: 4 });

        // ── 5. et ce n'est pas tout (14,4 → 18,0) : le crème monte, deux photos posées comme des tirages ──
        S.wipe(tl, "#s5", 13.95, { dir: "up", duration: 0.45, ease: S.ease.swift });
        tl.set("#s5", { clipPath: "none" }, 14.4);
        tl.fromTo("#cam5", { scale: 1.0, x: 0 }, { scale: 1.05, x: -12, duration: 3.8, ease: S.ease.glide }, 14.3);
        S.maskUp(tl, $$("#h5 .hd:nth-child(1) .st-word"), 14.4, { duration: 0.7 });
        S.maskUp(tl, $$("#h5 .hd:nth-child(2) .st-word"), 14.7, { duration: 0.7 });
        const ps = S.spring({ response: 0.6, damping: 0.78 });
        tl.fromTo("#pA", { y: 1500, rotation: -20 }, { y: 0, rotation: -5, duration: ps.duration, ease: ps.ease }, 14.55);
        tl.fromTo("#pB", { y: 1500, rotation: 18 }, { y: 0, rotation: 4, duration: ps.duration, ease: ps.ease }, 15.15);
        tl.fromTo("#pA img", { scale: 1.15 }, { scale: 1.0, duration: 3.5, ease: S.ease.glide }, 14.55);
        tl.fromTo("#pB img", { scale: 1.15 }, { scale: 1.0, duration: 3.0, ease: S.ease.glide }, 15.15);
        S.rise(tl, $$("#cA, #cB"), 15.0, { y: 14, blur: 6, duration: 0.6, stagger: 0.6, max: 0.6 });
        S.life(tl, $$(".pol .pimg"), 16.0, 18.1, { y: 3, x: 2, rotate: 0.25, period: 4, seed: 6 });

        // ── 6. l'appel (18,0 → 24,0) ──
        iris("#s6", "#rC", 540, 960, 1110, 17.5, 0.5);
        tl.fromTo("#cam6", { scale: 1.12 }, { scale: 1.0, duration: 6.5, ease: S.ease.glide }, 17.5);
        tl.fromTo("#glow6", { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 1.4, ease: S.ease.silk }, 18.0);
        const j6 = S.spring({ response: 0.55, damping: 0.8 });
        tl.fromTo("#jar6", { y: -900, rotation: 5 }, { y: 0, rotation: 0, duration: j6.duration, ease: j6.ease }, 17.85);
        tl.fromTo("#jar6 .jsh", { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.5, ease: S.ease.silk }, 18.0);
        S.converge(tl, $$("#brand .st-char"), 18.15, { spread: 40, duration: 0.9, stagger: 0.04 });
        S.rise(tl, "#k6", 18.5, { y: 12, blur: 6, duration: 0.6 });
        S.rise(tl, "#k7", 18.85, { y: 12, blur: 6, duration: 0.6 });
        tl.fromTo("#num", { opacity: 0 }, { opacity: 1, duration: 0.25, ease: S.ease.silk }, 18.95);
        $$("#num .strip").forEach((s, k) => {
          const d = +s.dataset.d;
          tl.fromTo(s, { y: 0, filter: "blur(4px)" }, { y: -(10 + d) * 128, filter: "blur(0px)", duration: 0.32 + k * 0.1, ease: S.ease.silk }, 19.0);
        });
        S.pop(tl, "#handle", 20.15, { from: 0.7, damping: 0.75 });
        S.sweep(tl, "#sh6", 21.2, { duration: 1.2 });
        S.life(tl, $("#jar6 img"), 19.0, TOTAL, { y: 6, x: 2, rotate: 0.5, period: 4, seed: 9 });
        S.life(tl, $$("#brand, #handle"), 20.6, TOTAL, { y: 3, x: 1, rotate: 0.1, period: 6, seed: 2 });

        // ── plateaux : chaque anneau part décalé et se cale, puis tout le plateau tourne lentement ──
        const trays = [["tA", 2.9, 1.3, 13], ["tB", 6.8, 1.4, 13], ["tC", 17.6, 1.5, 13]].map(([id, t0, d, n]) => {
          const rg = [...Array(n)].map((_, k) => $("#" + id + "r" + k)), spin = $("#" + id + "s");
          const off = rg.map((_, k) => (k % 2 ? 1 : -1) * (70 + 23 * k));
          return (t) => {
            const p = S.ease.silk(cl((t - t0) / d));
            rg.forEach((g, k) => g.setAttribute("transform", `rotate(${(off[k] * (1 - p)).toFixed(2)})`));
            spin.setAttribute("transform", `rotate(${((t - t0) * 6).toFixed(2)})`);
          };
        });

        // ── fumée de woussoulan : bouffées douces et rubans d'encens, en demi-résolution (adoucie par l'agrandissement) ──
        const sm = $("#smoke"), sx = sm.getContext("2d"), SW = 540, SH = 960, r = S.rng(21);
        const PUFF = [...Array(44)].map(() => ({ x: 0.18 + 0.64 * r(), life: 3.6 + 2.6 * r(), ph: r(), amp: 18 + 40 * r(), f: 0.5 + 0.8 * r(), size: 34 + 52 * r(), a: 0.05 + 0.06 * r(), s: r() * 6.28 }));
        const EMB = [...Array(26)].map(() => ({ x: 0.1 + 0.8 * r(), life: 2.2 + 2.2 * r(), ph: r(), sway: 6 + 14 * r(), f: 1 + 2 * r(), s: r() * 6.28 }));
        const WISP = [{ x: 0.40, ph: 0.0, w: 1.0 }, { x: 0.56, ph: 2.1, w: 0.8 }, { x: 0.48, ph: 4.2, w: 0.65 }];
        const AK = [[0, 0], [0.4, 1], [2.6, 1], [3.1, 0.55], [6.6, 0.55], [7.0, 0], [17.9, 0], [18.6, 0.45], [TOTAL, 0.45]];
        const alphaAt = (t) => { for (let i = 0; i < AK.length - 1; i++) { const [a, va] = AK[i], [b, vb] = AK[i + 1]; if (t <= b) return va + (vb - va) * S.ease.breath(cl((t - a) / (b - a))); } return 0; };
        const smoke = (t) => {
          const A = 2 * alphaAt(t); sx.clearRect(0, 0, SW, SH); if (A < 0.004) return;
          sx.globalCompositeOperation = "lighter";
          PUFF.forEach((p) => {
            const age = ((t / p.life + p.ph) % 1), y = SH * 1.06 - age * SH * 1.0;
            const x = p.x * SW + Math.sin(t * p.f + p.s) * p.amp * age + 30 * age * age * Math.sin(p.s * 3);
            const rad = p.size * (0.5 + 1.8 * age), al = A * p.a * Math.pow(Math.sin(Math.PI * age), 1.4);
            const g = sx.createRadialGradient(x, y, 0, x, y, rad);
            g.addColorStop(0, `rgba(255,232,208,${al.toFixed(4)})`); g.addColorStop(1, "rgba(255,232,208,0)");
            sx.fillStyle = g; sx.fillRect(x - rad, y - rad, rad * 2, rad * 2);
          });
          WISP.forEach((w) => {
            let px = 0, py = 0;
            for (let j = 0; j <= 56; j++) {
              const u = j / 56, y = SH * (1.0 - u * 0.86), amp = 3 + 70 * u * u;
              const x = w.x * SW + amp * Math.sin(u * 8.5 - t * 1.5 + w.ph) + 26 * u * Math.sin(u * 3.1 + t * 0.45 + w.ph);
              if (j > 0) {
                const fade = Math.sin(Math.PI * Math.min(1, u * 1.15)) * A * w.w;
                [[9 + 16 * u, 0.035], [3.5 + 6 * u, 0.06], [1.2 + 1.5 * u, 0.1]].forEach(([lw, al]) => {
                  sx.beginPath(); sx.moveTo(px, py); sx.lineTo(x, y); sx.lineWidth = lw; sx.lineCap = "round";
                  sx.strokeStyle = `rgba(255,238,220,${(al * fade).toFixed(4)})`; sx.stroke();
                });
              }
              px = x; py = y;
            }
          });
          EMB.forEach((e) => {
            const age = ((t / e.life + e.ph) % 1), y = SH * (1.02 - age * 0.9), x = e.x * SW + Math.sin(t * e.f + e.s) * e.sway;
            const al = A * Math.sin(Math.PI * age) * (0.55 + 0.45 * Math.sin(t * 9 + e.s * 5));
            sx.fillStyle = `rgba(255,190,90,${(0.8 * al).toFixed(3)})`; sx.beginPath(); sx.arc(x, y, 1.3, 0, 6.283); sx.fill();
            sx.fillStyle = `rgba(255,150,60,${(0.18 * al).toFixed(3)})`; sx.beginPath(); sx.arc(x, y, 4.5, 0, 6.283); sx.fill();
          });
          sx.globalCompositeOperation = "source-over";
        };

        // ── spray du flacon (12,0) : fines gouttelettes qui jaillissent de la buse, plus un voile de brume qui s'étale ──
        const mi = $("#mist"), mx = mi.getContext("2d"), r2 = S.rng(33), NOZ = [440, 600];
        const part = (n, o) => [...Array(n)].map(() => ({ a: (-60 + o.spread * (r2() - 0.5)) * Math.PI / 180, v: o.v[0] + o.v[1] * r2(), s: o.s[0] + o.s[1] * r2(),
          life: o.life[0] + o.life[1] * r2(), d: r2() * 0.1, al: o.al, g: o.g }));
        const DROP = [...part(220, { spread: 26, v: [380, 720], s: [1.2, 3.2], life: [0.5, 1.1], al: 0.9, g: 2.0 }),
                      ...part(14, { spread: 36, v: [240, 320], s: [22, 34], life: [1.2, 1.2], al: 0.05, g: 3.0 })];
        const mist = (t) => {
          mx.clearRect(0, 0, 1080, 1920); const age0 = t - 12.0; if (age0 < 0 || age0 > 2.6) return;
          mx.globalCompositeOperation = "lighter";
          DROP.forEach((p) => {
            const age = age0 - p.d; if (age < 0 || age > p.life) return;
            const k = 1 - Math.exp(-age * 3.2), dist = p.v * k / 3.2;
            const x = NOZ[0] + Math.cos(p.a) * dist + 30 * age * age, y = NOZ[1] + Math.sin(p.a) * dist - 30 * age + 60 * age * age * (p.s < 5 ? 1 : 0);
            const rad = p.s * (0.35 + p.g * k), al = p.al * Math.pow(1 - age / p.life, 1.5);
            const g = mx.createRadialGradient(x, y, 0, x, y, rad);
            g.addColorStop(0, `rgba(255,242,226,${al.toFixed(4)})`); g.addColorStop(1, "rgba(255,242,226,0)");
            mx.fillStyle = g; mx.fillRect(x - rad, y - rad, rad * 2, rad * 2);
          });
          mx.globalCompositeOperation = "source-over";
        };

        S.drive(tl, 0, TOTAL, [...trays, smoke, mist, S.grain($("#grain"), { fps: 60, seed: 8 })]);
'''
open(f'{P}/index.html', 'w').write(HTML.replace('%%JS%%', JS))
print('ok', TOTAL)
