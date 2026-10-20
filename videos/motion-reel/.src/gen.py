# « MOHAMED — MOTION REEL 2026 » : pub pour ses services, format « écran dans l'écran » (référence : reel @danyltn).
# Vertical 1080×1920, 60 i/s. En haut deux pastilles (sujet + créateur), au centre une carte 16:9 qui joue un showreel de
# 16 s (8 mesures à 120 BPM, une partie par mesure, coupes sur la mesure, habillage technique : timecode, mesures,
# réglages), en bas l'accroche lisible sans le son. Système de motion : videos/_studio (studio.js).
import os, json, math
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 60
R0 = 0.6                    # le showreel démarre quand la carte est posée
BAR = 2.0                   # 120 BPM : 1 mesure = 2 s
TOTAL = round(R0 + 8 * BAR + 0.8, 2)
ORANGE, BLUE, LIME, INK, CREAM = '#FF4F1F', '#2340FF', '#D7FF3A', '#141414', '#F3EBDD'

# ── formes du morphing : 72 points sur des rayons communs, pour passer de l'une à l'autre point par point ──
N = 72
def ray_poly(verts, th):
    dx, dy, best = math.cos(th), math.sin(th), None
    for i in range(len(verts)):
        (x1, y1), (x2, y2) = verts[i], verts[(i + 1) % len(verts)]
        ex, ey = x2 - x1, y2 - y1
        den = dx * ey - dy * ex
        if abs(den) < 1e-9: continue
        t, u = (x1 * ey - y1 * ex) / den, (x1 * dy - y1 * dx) / den
        if t > 0 and -1e-9 <= u <= 1 + 1e-9 and (best is None or t < best): best = t
    return best
def poly(n, r, a0=-90, inner=None):
    vs = []
    for k in range(n * (2 if inner else 1)):
        rr = (r if k % 2 == 0 else inner) if inner else r
        a = math.radians(a0 + k * 360 / (n * (2 if inner else 1)))
        vs.append((rr * math.cos(a), rr * math.sin(a)))
    return vs
def sample(fn):
    return [[round(fn(-math.pi / 2 + 2 * math.pi * k / N) * math.cos(-math.pi / 2 + 2 * math.pi * k / N), 1),
             round(fn(-math.pi / 2 + 2 * math.pi * k / N) * math.sin(-math.pi / 2 + 2 * math.pi * k / N), 1)] for k in range(N)]
SHAPES = {'circle': sample(lambda th: 190),
          'triangle': sample(lambda th: ray_poly(poly(3, 235), th)),
          'star': sample(lambda th: ray_poly(poly(5, 235, inner=100), th)),
          'square': sample(lambda th: ray_poly(poly(4, 215, a0=-135), th))}

# ── étoile de la marque (fin) : 10 branches de longueurs un peu irrégulières ──
ARMS = ''.join(f'<line x1="0" y1="0" x2="{round(math.cos(math.radians(k * 36 + 8)) * L, 1)}" y2="{round(math.sin(math.radians(k * 36 + 8)) * L, 1)}"/>'
               for k, L in enumerate([92, 78, 96, 84, 90, 80, 95, 76, 88, 86]))

EASE_ROWS = [('LINÉAIRE', 'none', '#9B958C'), ('EASE-IN', 'power2.in', ORANGE), ('EASE-OUT', 'power2.out', ORANGE),
             ('SILK', 'silk', ORANGE), ('OVERSHOOT', 'overshoot', ORANGE), ('RESSORT', 'spring', BLUE)]
ADS = [('nessa', 'Nessa Paris', 'BEAUTÉ'), ('sensexpress', 'SensExpress', "PARFUM D'AMBIANCE"), ('cassia', 'Cassia Dressing', 'MODE'),
       ('founerou', "Founerou Grill's", 'RESTAURANT'), ('gimso', 'GimSo', 'PUB TIKTOK'), ('skprint', 'SK Print', 'IMPRESSION')]
WORDS = [('FLUIDE.', ORANGE, INK), ('PRÉCIS.', '#FFFFFF', BLUE), ('JAMAIS', LIME, INK), ('LINÉAIRE', INK, '#FFFFFF')]
SECTIONS = ['01 — EASING', '02 — MORPHING', '03 — PUBS · LUXE', '04 — PUBS · STREET', '05 — MOTIFS', '06 — 3D', '07 — TYPO', '08 — FIN']
# couleur de l'habillage selon le fond (par mesure, et par mot pendant la typo)
HUD = [(0, INK), (1, '#FFFFFF'), (2, '#FFFFFF'), (3, INK), (4, '#FFFFFF'), (5, '#FFFFFF'), (6, INK), (6.25, BLUE), (6.5, INK), (6.75, '#FFFFFF'), (7, INK)]

rows = ''.join(f'''
          <div class="row" style="top:{250 + i * 96}px"><span class="lab">{lab}</span><i class="trk"></i><b class="dot" id="d{i}" data-hf-motion-blur='{{"samplesPerFrame": 8}}' style="background:{col}"></b></div>''' for i, (lab, e, col) in enumerate(EASE_ROWS))
trio = {}
for s, base in ((2, 0), (3, 3)):
    ads = ''
    for j in range(3):
        k, name, sector = ADS[base + j]
        x = 177 + j * 432
        ads += f'''
        <div class="ad" id="ad{base + j}" style="left:{x}px"><video id="v{base + j}" class="clip vid" src="assets/clips/{k}.mp4" data-start="{R0 + s * BAR}" data-duration="{BAR}" data-track-index="{3 + j}" muted playsinline></video></div>
        <div class="adl" id="al{base + j}" style="left:{x}px"><em>{name}</em><span>{sector}</span></div>'''
    trio[s] = ads
words = ''.join(f'''
        <div class="wbg" id="wb{i}" style="background:{bg}"><div class="word" id="w{i}" data-hf-motion-blur='{{"samplesPerFrame": 8}}' style="color:{fg}">{t}{'<i style="color:' + ORANGE + '">.</i>' if t == 'LINÉAIRE' else ''}</div></div>''' for i, (t, bg, fg) in enumerate(WORDS))
name = ''.join(f'<span id="n{i}">{c}</span>' for i, c in enumerate('MOHAMED'))
secs = ''.join(f'<span id="sl{i}">{t}</span>' for i, t in enumerate(SECTIONS))
barsq = ''.join('<i></i>' for _ in range(8))

HTML = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/studio.js"></script>
    <link rel="stylesheet" href="assets/vendor/studio.css" />
    <style>
      @font-face {{ font-family: "Archivo Black"; src: url("assets/fonts/archivo-black-latin-400-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Instrument Serif"; font-style: italic; src: url("assets/fonts/instrument-serif-latin-400-italic.woff2") format("woff2"); }}
      @font-face {{ font-family: "Instrument Serif"; font-style: normal; src: url("assets/fonts/instrument-serif-latin-400-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 600; src: url("assets/fonts/inter-latin-600-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 800; src: url("assets/fonts/inter-latin-800-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #0A090B; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #0A090B; font-family: "Inter", sans-serif; }}
      #glow {{ position: absolute; left: -260px; top: 900px; width: 1600px; height: 1300px; border-radius: 50%; background: radial-gradient(closest-side, rgba(255,79,31,0.30), rgba(255,79,31,0.08) 55%, rgba(255,79,31,0)); }}
      .pill {{ position: absolute; left: 56px; top: 318px; height: 82px; padding: 0 34px; border-radius: 41px; background: {CREAM}; display: flex; align-items: center; gap: 16px; font: 800 34px "Inter"; color: #111; }}
      .pill i {{ width: 18px; height: 18px; border-radius: 9px; background: {ORANGE}; }}
      .me {{ position: absolute; right: 56px; top: 308px; width: 420px; height: 102px; border-radius: 24px; background: {CREAM}; display: flex; align-items: center; gap: 18px; padding: 0 20px; }}
      .me b {{ width: 66px; height: 66px; border-radius: 33px; background: {ORANGE}; color: #fff; font: 400 34px "Archivo Black"; display: flex; align-items: center; justify-content: center; }}
      .me div {{ display: flex; flex-direction: column; gap: 2px; }}
      .me strong {{ font: 800 32px "Inter"; color: #111; }}
      .me span {{ font: 600 23px "Inter"; color: #5F5A54; }}
      #card {{ position: absolute; left: 40px; top: 500px; width: 1000px; height: 563px; border-radius: 30px; overflow: hidden; box-shadow: 0 0 0 1px rgba(255,255,255,0.06), 0 0 90px rgba(255,79,31,0.32), 0 40px 90px rgba(0,0,0,0.6); }}
      #stage {{ position: absolute; left: 0; top: 0; width: 1600px; height: 900px; transform: scale(0.625); transform-origin: 0 0; overflow: hidden; background: {INK}; }}
      .kick {{ position: absolute; left: 60px; top: 1150px; font: 500 28px "Plex Mono"; letter-spacing: 0.2em; color: {ORANGE}; white-space: nowrap; }}
      .hl {{ position: absolute; left: 56px; font: 400 104px/1 "Archivo Black"; color: {CREAM}; letter-spacing: -0.02em; white-space: nowrap; }}
      .hl em {{ font: italic 400 118px/1 "Instrument Serif"; color: {ORANGE}; letter-spacing: 0; }}
      #hl3 {{ color: {INK}; }}
      #box {{ position: absolute; left: 44px; top: 1418px; width: 772px; height: 118px; background: {ORANGE}; border-radius: 8px; transform-origin: 0 50%; }}
      .sub {{ position: absolute; left: 60px; top: 1580px; font: 500 24px "Plex Mono"; letter-spacing: 0.14em; color: #8E877E; white-space: nowrap; }}
      /* — showreel (repère 1600×900) — */
      .sec {{ position: absolute; inset: 0; visibility: hidden; opacity: 0; overflow: hidden; }}
      .mono {{ font: 500 18px "Plex Mono"; letter-spacing: 0.14em; white-space: nowrap; }}
      #s0 {{ background: #EFEAE0; color: {INK}; }}
      #s0 h2 {{ position: absolute; left: 92px; top: 92px; font: italic 400 76px/1 "Instrument Serif"; }}
      #s0 .note {{ position: absolute; right: 92px; top: 128px; }}
      .row {{ position: absolute; left: 92px; right: 92px; height: 40px; }}
      .row .lab {{ position: absolute; left: 0; top: 10px; font: 500 18px "Plex Mono"; letter-spacing: 0.14em; color: #3A3732; }}
      .row .trk {{ position: absolute; left: 330px; right: 0; top: 19px; height: 2px; background: repeating-linear-gradient(90deg, rgba(20,20,20,0.35) 0 2px, transparent 2px 40px); }}
      .dot {{ position: absolute; left: 316px; top: 6px; width: 28px; height: 28px; border-radius: 14px; }}
      .ab {{ position: absolute; top: 212px; font: 500 18px "Plex Mono"; color: #3A3732; }}
      #s1 {{ background: {BLUE}; color: #fff; }}
      #s1 svg {{ position: absolute; left: 0; top: 0; }}
      .cross {{ position: absolute; background: rgba(255,255,255,0.22); }}
      #s2 {{ background: #101012; color: #fff; }}
      #s3 {{ background: {ORANGE}; color: {INK}; }}
      .ad {{ position: absolute; top: 96px; width: 382px; height: 680px; border-radius: 18px; overflow: hidden; background: #000; box-shadow: 0 30px 60px rgba(0,0,0,0.45); }}
      .vid {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; object-fit: cover; }}
      .adl {{ position: absolute; top: 792px; width: 382px; display: flex; justify-content: space-between; align-items: baseline; }}
      .adl em {{ font: italic 400 36px "Instrument Serif"; }}
      .adl span {{ font: 500 14px "Plex Mono"; letter-spacing: 0.14em; opacity: 0.75; }}
      #s4, #s5 {{ background: #0B0B0D; }}
      #s4 canvas, #s5 canvas {{ position: absolute; left: 0; top: 0; }}
      .wbg {{ position: absolute; inset: 0; visibility: hidden; display: flex; align-items: center; justify-content: center; }}
      .word {{ font: 400 232px/1 "Archivo Black"; letter-spacing: -0.03em; white-space: nowrap; }}
      #s7 {{ background: {ORANGE}; color: {INK}; }}
      #mark {{ position: absolute; left: 230px; top: 300px; overflow: visible; }}
      #mark line {{ stroke: {INK}; stroke-width: 30; stroke-linecap: round; }}
      #nm {{ position: absolute; left: 430px; top: 292px; font: 400 196px/1 "Archivo Black"; letter-spacing: -0.03em; white-space: nowrap; }}
      #nm span {{ display: inline-block; }}
      #md {{ position: absolute; left: 438px; top: 500px; font: italic 400 96px/1 "Instrument Serif"; white-space: nowrap; }}
      #rule {{ position: absolute; left: 200px; right: 200px; top: 660px; height: 2px; background: {INK}; transform-origin: 0 50%; }}
      #fine {{ position: absolute; left: 200px; right: 200px; top: 684px; display: flex; justify-content: space-between; font: 500 15px "Plex Mono"; letter-spacing: 0.14em; }}
      /* habillage technique */
      #hud {{ position: absolute; inset: 0; color: {INK}; pointer-events: none; }}
      .cor {{ position: absolute; width: 30px; height: 30px; border-color: currentColor; border-style: solid; }}
      #hud .tl {{ position: absolute; left: 70px; top: 40px; }}
      #hud .tr {{ position: absolute; right: 70px; top: 40px; }}
      #hud .tr span {{ position: absolute; right: 0; top: 0; opacity: 0; }}
      #hud .bl {{ position: absolute; left: 70px; bottom: 40px; }}
      #hud .br {{ position: absolute; right: 70px; bottom: 40px; display: flex; gap: 14px; align-items: center; }}
      #bars {{ display: flex; gap: 5px; }}
      #bars i {{ width: 14px; height: 14px; border: 2px solid currentColor; }}
      #beat {{ width: 12px; height: 12px; border-radius: 6px; background: currentColor; }}
      #prog {{ position: absolute; left: 0; bottom: 0; width: 1600px; height: 4px; background: currentColor; transform-origin: 0 50%; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
      <div id="frame" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0">
        <div id="glow"></div>
        <div class="pill" id="pill"><i></i>Showreel · Motion design</div>
        <div class="me" id="me"><b>M</b><div><strong>Mohamed</strong><span>Motion design · Bamako</span></div></div>
        <div id="card"><div id="stage">
          <div class="sec" id="s0"><h2>Six façons d'aller de A à B.</h2><div class="mono note">MÊME DISTANCE · MÊME DURÉE (1,2 S)</div>
            <div class="ab" style="left:420px">A</div><div class="ab" style="right:92px">B</div>{rows}
          </div>
          <div class="sec" id="s1"><div class="cross" style="left:800px; top:120px; width:1px; height:660px"></div><div class="cross" style="left:200px; top:450px; width:1200px; height:1px"></div>
            <svg width="1600" height="900"><g transform="translate(800 450)"><path id="echo" fill="none" stroke="{ORANGE}" stroke-width="3" opacity="0.8"/><path id="shape" fill="#F4F1EA"/></g><g id="ring"></g></svg>
            <div class="mono" style="position:absolute; left:200px; top:480px">MORPH <span id="mlab">CERCLE</span></div>
            <div class="mono" style="position:absolute; right:200px; top:480px">ROT <span id="mrot">0.0</span>° · RESSORT ζ=0.42</div>
          </div>
          <div class="sec" id="s2">{trio[2]}
          </div>
          <div class="sec" id="s3">{trio[3]}
          </div>
          <div class="sec" id="s4"><canvas id="tru" width="1600" height="900"></canvas></div>
          <div class="sec" id="s5"><canvas id="pts" width="1600" height="900"></canvas><div class="mono" style="position:absolute; left:200px; top:780px; color:#fff">POINTS 900 · <span id="plab">SPHÈRE</span></div></div>
          <div class="sec" id="s6">{words}
          </div>
          <div class="sec" id="s7"><svg id="mark" width="200" height="200" viewBox="0 0 200 200"><g id="mk" transform="translate(100 100)">{ARMS}</g></svg>
            <div id="nm">{name}</div><div id="md">motion designer</div><div id="rule"></div>
            <div id="fine"><span>SHOWREEL 2026</span><span>16 SECONDES</span><span>CHAQUE IMAGE CRÉÉE EN CODE</span><span>DISPONIBLE POUR VOS PROJETS</span></div>
          </div>
          <div id="hud">
            <div class="cor" style="left:24px; top:24px; border-width:3px 0 0 3px"></div><div class="cor" style="right:24px; top:24px; border-width:3px 3px 0 0"></div>
            <div class="cor" style="left:24px; bottom:24px; border-width:0 0 3px 3px"></div><div class="cor" style="right:24px; bottom:24px; border-width:0 3px 3px 0"></div>
            <div class="mono tl"><b>MOHAMED</b>&nbsp;&nbsp;&nbsp;MOTION REEL — 2026</div>
            <div class="mono tr">{secs}</div>
            <div class="mono bl"><span id="tc">00:00:00:00</span>&nbsp;&nbsp;&nbsp;60 FPS</div>
            <div class="mono br">120 BPM <span id="bars">{barsq}</span> <span id="barn">BAR 1/8</span> <span id="beat"></span></div>
            <div id="prog"></div>
          </div>
        </div></div>
        <div class="kick" id="kick">× 100 % CRÉÉ EN CODE · SANS AFTER EFFECTS ×</div>
        <div class="hl" id="hl1" style="top:1196px">Votre marque</div>
        <div class="hl" id="hl2" style="top:1302px"><span class="st-mask"><span class="st-word">mérite</span></span> <span class="st-mask"><em class="st-word">une vraie</em></span></div>
        <div id="box"></div>
        <div class="hl" id="hl3" style="top:1426px">&nbsp;pub vidéo.</div>
        <div class="sub" id="sub">SITES · APPLICATIONS · PUBS VIDÉO — BAMAKO</div>
        <canvas id="grain" class="st-grain" width="{W}" height="{H}" style="opacity:0.05"></canvas>
      </div>
      <audio id="music" src="assets/music.wav" data-start="{R0}" data-duration="{round(TOTAL - R0, 2)}" data-track-index="10" data-volume="0.9"></audio>
      <audio id="sfx0" src="assets/whoosh.wav" data-start="0.05" data-duration="0.55" data-track-index="11" data-volume="0.45"></audio>
      <audio id="sfx1" src="assets/impact.wav" data-start="{R0 + 7 * BAR}" data-duration="1.2" data-track-index="12" data-volume="0.5"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      (function () {{
        const S = STUDIO, $ = (q) => document.querySelector(q), $$ = (q) => Array.from(document.querySelectorAll(q));
        const tl = gsap.timeline({{ paused: true }});
        const R0 = {R0}, BAR = {BAR}, BEAT = BAR / 4, at = (bar, beat = 0) => R0 + bar * BAR + beat * BEAT;
%%JS%%
        tl.to({{}}, {{ duration: {TOTAL} }}, 0);
        window.__timelines["main"] = tl;
      }})();
    </script>
%%MB%%
  </body>
</html>
'''
JS = r'''
        // ── cadre : la carte se pose, les pastilles et l'accroche arrivent, puis tout respire ──
        tl.fromTo("#glow", { opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: 1.4, ease: S.ease.silk }, 0);
        S.pop(tl, ["#pill", "#me"], 0.08, { from: 0.7, y: -20, damping: 0.75, response: 0.45, stagger: 0.1 });
        tl.fromTo("#card", { scale: 0.88, opacity: 0, filter: "blur(18px)" }, { scale: 1, opacity: 1, filter: "blur(0px)", duration: 0.8, ease: S.ease.silk }, 0);
        S.rise(tl, S.split($("#kick")), 0.3, { y: 14, blur: 6, stagger: 0.012, duration: 0.6, max: 0.4 });
        S.maskUp(tl, S.split($("#hl1"), { by: "words", mask: true }), 0.42, { duration: 0.8 });
        S.maskUp(tl, $$("#hl2 .st-word"), 0.55, { duration: 0.8 });
        tl.fromTo("#box", { scaleX: 0 }, { scaleX: 1, duration: 0.55, ease: S.ease.swift }, 0.72);
        S.maskUp(tl, S.split($("#hl3"), { by: "words", mask: true }), 0.82, { duration: 0.7 });
        tl.fromTo("#sub", { opacity: 0 }, { opacity: 1, duration: 0.6, ease: S.ease.breath }, 1.1);
        S.life(tl, [$("#card")], 1.0, TOTAL, { x: 0, y: 4, rotate: 0.15, scale: 0.003, period: 6, seed: 3 });
        S.life(tl, [$("#pill"), $("#me")], 1.0, TOTAL, { x: 2, y: 3, rotate: 0.3, scale: 0.004, period: 5, seed: 7 });
        tl.fromTo("#glow", { scale: 1 }, { scale: 1.06, duration: 2.0, ease: S.ease.breath, yoyo: true, repeat: 7, immediateRender: false }, 1.4);

        // ── sections : coupe franche sur chaque mesure ──
        for (let i = 0; i < 8; i++) {
          tl.set("#s" + i, { autoAlpha: 1 }, at(i));
          if (i < 7) tl.set("#s" + i, { autoAlpha: 0 }, at(i + 1));
          tl.set("#sl" + i, { opacity: 1 }, at(i)); if (i < 7) tl.set("#sl" + i, { opacity: 0 }, at(i + 1));
        }
        HUDC.forEach(([b, c]) => tl.set("#hud", { color: c }, at(Math.floor(b), (b % 1) * 4)));

        // habillage : timecode, mesures, temps, barre de progression (fonction pure du temps)
        const tc = $("#tc"), sq = $$("#bars i"), barn = $("#barn"), beat = $("#beat"), prog = $("#prog");
        const hud = (t) => {
          const lt = Math.max(0, t - R0), f = Math.floor(lt * 60 + 1e-6), b = Math.min(7, Math.floor(lt / BAR));
          tc.textContent = "00:00:" + String(Math.floor(f / 60)).padStart(2, "0") + ":" + String(f % 60).padStart(2, "0");
          sq.forEach((e, i) => { e.style.background = i <= b ? "currentColor" : "transparent"; });
          barn.textContent = "BAR " + (b + 1) + "/8";
          beat.style.opacity = (lt % BEAT) < 0.12 ? 1 : 0.25;
          prog.style.transform = "scaleX(" + Math.min(1, lt / (8 * BAR)).toFixed(4) + ")";
        };

        // ── 01 · easing : six courbes, même distance, même durée ──
        const spr = S.spring({ response: 0.5, damping: 0.42 }).ease;
        EASES.forEach((e, i) => tl.fromTo("#d" + i, { x: 0 }, { x: 1044, duration: 1.2, ease: e === "spring" ? spr : (S.ease[e] || e) }, at(0, 0.6)));
        S.rise(tl, $("#s0 h2"), at(0), { y: 20, blur: 8, duration: 0.6 });

        // ── 02 · morphing : cercle → triangle → étoile → carré sur les temps, ressort et écho ──
        const SH = SHAPES, SEQ = [["circle", "CERCLE"], ["triangle", "CERCLE → TRIANGLE"], ["star", "TRIANGLE → ÉTOILE"], ["square", "ÉTOILE → CARRÉ"]];
        const mE = S.spring({ response: 0.42, damping: 0.42 }).ease, MD = 0.45, shapePath = $("#shape"), echo = $("#echo");
        const ring = $("#ring"), NS = "http://www.w3.org/2000/svg", tris = [];
        for (let k = 0; k < 10; k++) { const p = document.createElementNS(NS, "polygon"); p.setAttribute("points", "0,-15 13,10 -13,10"); p.setAttribute("fill", "#F4F1EA"); ring.appendChild(p); tris.push(p); }
        const morphAt = (lt) => {
          let i = 0; while (i < 3 && lt >= (i + 1) * BEAT) i++;
          if (i === 0) return { pts: SH.circle, rot: 0, lab: SEQ[0][1] };
          const a = SH[SEQ[i - 1][0]], b = SH[SEQ[i][0]], p = mE(Math.min(1, Math.max(0, (lt - i * BEAT) / MD)));
          return { pts: a.map((q, k) => [q[0] + (b[k][0] - q[0]) * p, q[1] + (b[k][1] - q[1]) * p]), rot: 72 * (i - 1) + 72 * p, lab: SEQ[i][1] };
        };
        const d = (m, s) => "M" + m.pts.map((q) => { const r = m.rot * Math.PI / 180, c = Math.cos(r), n = Math.sin(r); return ((q[0] * c - q[1] * n) * s).toFixed(1) + " " + ((q[0] * n + q[1] * c) * s).toFixed(1); }).join("L") + "Z";
        const morph = (t) => {
          const lt = t - at(1); if (lt < -0.01 || lt > BAR + 0.01) return;
          const pop = S.ease.overshoot(Math.min(1, Math.max(0, lt / 0.35)));
          const m = morphAt(lt), e = morphAt(Math.max(0, lt - 0.08));
          shapePath.setAttribute("d", d(m, pop)); echo.setAttribute("d", d(e, pop * 1.04));
          $("#mlab").textContent = m.lab; $("#mrot").textContent = m.rot.toFixed(1);
          tris.forEach((p, k) => { const a = lt * 0.9 + k * Math.PI / 5, x = 800 + Math.cos(a) * 340 * pop, y = 450 + Math.sin(a) * 300 * pop; p.setAttribute("transform", "translate(" + x.toFixed(1) + " " + y.toFixed(1) + ") rotate(" + (a * 57.3 + 90).toFixed(1) + ")"); });
        };

        // ── 03 / 04 · vos pubs : trois vidéos qui montent sur ressort ──
        [[2, [0, 1, 2]], [3, [3, 4, 5]]].forEach(([bar, ids]) => {
          S.pop(tl, ids.map((i) => "#ad" + i), at(bar), { from: 0.9, y: 140, damping: 0.72, response: 0.5, stagger: 0.07 });
          S.rise(tl, ids.map((i) => "#al" + i), at(bar, 0.6), { y: 16, blur: 6, stagger: 0.07, duration: 0.6 });
        });

        // ── 05 · motifs : tuiles de Truchet qui pivotent en vagues depuis le centre ──
        const tru = $("#tru").getContext("2d"), hash = (a, b, c) => { let h = (a * 73856093) ^ (b * 19349663) ^ (c * 83492791); h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
        const truchet = (t) => {
          const lt = t - at(4); if (lt < -0.01 || lt > BAR + 0.01) return;
          tru.fillStyle = "#0B0B0D"; tru.fillRect(0, 0, 1600, 900); tru.lineWidth = 18; tru.lineCap = "butt";
          for (let gy = 1; gy < 8; gy++) for (let gx = 0; gx < 16; gx++) {  // rangées du haut et du bas laissées noires : l'habillage reste lisible
            const dist = Math.hypot(gx - 7.5, gy - 4) * 0.045; let rot = (hash(gx, gy, 1) < 0.5 ? 0 : 1) * Math.PI / 2;
            for (let w = 0; w < 4; w++) rot += S.ease.silk(Math.min(1, Math.max(0, (lt - w * BEAT - dist) / 0.32))) * Math.PI / 2;
            tru.save(); tru.translate(gx * 100 + 50, gy * 100 + 50); tru.rotate(rot);
            tru.strokeStyle = lt > 2 * BEAT && hash(gx, gy, 2) < 0.3 ? "#FF4F1F" : "#F4F1EA";
            tru.beginPath(); tru.arc(-50, -50, 50, 0, Math.PI / 2); tru.stroke();
            tru.beginPath(); tru.arc(50, 50, 50, Math.PI, Math.PI * 1.5); tru.stroke(); tru.restore();
          }
        };

        // ── 06 · 3D : 900 points, sphère qui devient un tore, en rotation ──
        const pts = $("#pts").getContext("2d"), NP = 900, SPH = [], TOR = [];
        for (let k = 0; k < NP; k++) {
          const y = 1 - 2 * (k + 0.5) / NP, r = Math.sqrt(1 - y * y), ph = k * 2.399963; SPH.push([r * Math.cos(ph), y, r * Math.sin(ph)]);
          const u = 2 * Math.PI * ((k * 0.618034) % 1), v = 2 * Math.PI * k / NP * 23; TOR.push([(0.78 + 0.3 * Math.cos(v)) * Math.cos(u), 0.3 * Math.sin(v), (0.78 + 0.3 * Math.cos(v)) * Math.sin(u)]);
        }
        const cloud = (t) => {
          const lt = t - at(5); if (lt < -0.01 || lt > BAR + 0.01) return;
          pts.fillStyle = "#0B0B0D"; pts.fillRect(0, 0, 1600, 900);
          const m = S.ease.glide(Math.min(1, Math.max(0, (lt - 0.8) / 0.7))), grow = S.ease.silk(Math.min(1, lt / 0.6));
          const ry = lt * 1.2, rx = 0.45 + 0.25 * m, cy = Math.cos(ry), sy = Math.sin(ry), cx = Math.cos(rx), sx = Math.sin(rx);
          $("#plab").textContent = m < 0.5 ? "SPHÈRE" : "SPHÈRE → TORE";
          for (let k = 0; k < NP; k++) {
            const a = SPH[k], b = TOR[k]; let x = (a[0] + (b[0] - a[0]) * m) * grow, y = (a[1] + (b[1] - a[1]) * m) * grow, z = (a[2] + (b[2] - a[2]) * m) * grow;
            const x1 = x * cy + z * sy, z1 = -x * sy + z * cy, y1 = y * cx - z1 * sx, z2 = y * sx + z1 * cx;
            const f = 620 / (z2 + 2.8), px = 800 + x1 * f * 1.3, py = 430 + y1 * f * 1.3, s = Math.max(1.2, 4.2 * f / 300);
            pts.globalAlpha = 0.35 + 0.65 * (1 - (z2 + 1) / 2); pts.fillStyle = k % 9 === 0 ? "#FF4F1F" : "#F4F1EA";
            pts.beginPath(); pts.arc(px, py, s, 0, 6.2832); pts.fill();
          }
          pts.globalAlpha = 1;
        };

        // ── 07 · typo : un mot par temps, qui claque (écrasement + flou de mouvement) ──
        for (let i = 0; i < 4; i++) {
          tl.set("#wb" + i, { visibility: "visible" }, at(6, i)); if (i < 3) tl.set("#wb" + i, { visibility: "hidden" }, at(6, i + 1));
          tl.fromTo("#w" + i, { scaleX: 1.35, scaleY: 0.25, y: 80, opacity: 0 }, { scaleX: 1, scaleY: 1, y: 0, opacity: 1, duration: 0.28, ease: S.ease.overshoot }, at(6, i));
        }

        // ── 08 · fin : l'étoile tourne et se pose, MOHAMED se décode lettre par lettre ──
        const mk = S.spring({ response: 0.5, damping: 0.6 });
        tl.fromTo("#mark", { scale: 0, rotation: -160 }, { scale: 1, rotation: 0, duration: mk.duration, ease: mk.ease }, at(7));
        tl.fromTo("#mark", { rotation: 0 }, { rotation: 40, duration: BAR - 0.6, ease: "none", immediateRender: false }, at(7, 1.2));
        const GL = "ABCDEFGHJKLMNPRSTUVWXYZ#%&*", letters = $$("#nm span"), FINAL = "MOHAMED";
        const decode = (t) => {
          letters.forEach((el, i) => {
            const s0 = at(7, 0.5) + i * 0.05, f = Math.floor(t * 60);
            if (t < s0) { el.style.opacity = 0; return; }
            el.style.opacity = 1; el.textContent = t < s0 + 0.28 ? GL[Math.floor(hash(f, i, 7) * GL.length)] : FINAL[i];
          });
        };
        S.rise(tl, "#md", at(7, 1.4), { y: 24, blur: 10, duration: 0.8 });
        tl.fromTo("#rule", { scaleX: 0 }, { scaleX: 1, duration: 0.7, ease: S.ease.swift }, at(7, 1.8));
        S.rise(tl, $$("#fine span"), at(7, 2.0), { y: 10, blur: 4, stagger: 0.06, duration: 0.5 });

        // un seul pilote pour tout ce qui se dessine image par image (seek-safe)
        S.drive(tl, 0, TOTAL, [hud, morph, truchet, cloud, decode, S.grain($("#grain"), { fps: 60, seed: 5 })]);
'''
JS = JS.replace('HUDC', json.dumps(HUD)).replace('EASES', json.dumps([e for _, e, _ in EASE_ROWS])).replace('SHAPES', json.dumps(SHAPES)).replace('TOTAL', str(TOTAL))
HTML = HTML.replace('%%JS%%', JS).replace('%%MB%%', open(f'{P}/compositions/components/motion-blur.html').read())
open(f'{P}/index.html', 'w').write(HTML)
print('ok', TOTAL)
