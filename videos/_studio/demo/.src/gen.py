# Démo du système Studio (videos/_studio) : 9 s, 1080×1920. Caméra 2.5D avec parallaxe et mise au point,
# texte découpé en lettres et en mots masqués, ressort physique, vie continue, reflet, flou de mouvement
# (composant officiel motion-blur), traversée entre scènes, grain et vignette.
import os, shutil
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.dirname(P)
for f in ('studio.js', 'studio.css'): shutil.copy(f'{ST}/{f}', f'{P}/assets/vendor/{f}')
W, H, TOTAL = 1080, 1920, 9.0
MB = open(f'{P}/compositions/components/motion-blur.html').read()
BOKEH = [(90, 300, 180, 'orange'), (880, 420, 120, 'white'), (760, 1500, 220, 'orange'), (140, 1650, 140, 'white'), (980, 1040, 90, 'orange'),
         (40, 980, 70, 'white'), (600, 1780, 110, 'white'), (330, 140, 80, 'orange'), (930, 1780, 60, 'orange')]
bokeh = ''.join(f'<i class="bk" style="left:{x}px; top:{y}px; width:{d}px; height:{d}px; background: radial-gradient(circle, {"rgba(255,120,60,0.55)" if c == "orange" else "rgba(255,240,225,0.4)"}, rgba(0,0,0,0) 70%)"></i>' for x, y, d, c in BOKEH)
html = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/studio.js"></script>
    <link rel="stylesheet" href="assets/vendor/studio.css" />
    <style>
      @font-face {{ font-family: "Inter"; font-weight: 800; src: url("assets/fonts/inter-latin-800-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 900; src: url("assets/fonts/inter-latin-900-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #0A0A0C; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #0A0A0C; font-family: "Inter", sans-serif; }}
      .scene {{ position: absolute; inset: 0; }}
      #grid {{ position: absolute; inset: -200px; background-image: radial-gradient(rgba(244,242,238,0.12) 1.6px, transparent 1.7px); background-size: 44px 44px; }}
      .blob {{ position: absolute; border-radius: 50%; }}
      .bk {{ position: absolute; border-radius: 50%; }}
      #ph {{ position: absolute; left: 290px; top: 640px; width: 500px; height: 1040px; border-radius: 70px; padding: 12px; background: #121216; }}
      #ph .scr {{ position: relative; width: 100%; height: 100%; border-radius: 58px; overflow: hidden; background: #000; }}
      #ph img {{ width: 100%; display: block; }}
      .kick {{ position: absolute; left: 0; right: 0; text-align: center; font: 500 30px "Plex Mono"; color: #FF5A1F; letter-spacing: 0.12em; }}
      .h {{ position: absolute; left: 0; right: 0; text-align: center; font: 800 96px/1.05 "Inter"; color: #F4F2EE; letter-spacing: -0.04em; white-space: nowrap; }}
      .pill {{ position: absolute; left: 50%; width: 520px; margin-left: -260px; height: 128px; border-radius: 64px; background: #17171B; display: flex; align-items: center; gap: 26px; padding: 0 44px; font: 800 60px "Inter"; color: #F4F2EE; letter-spacing: -0.03em; }}
      .pill i {{ width: 22px; height: 22px; border-radius: 11px; background: #FF5A1F; box-shadow: 0 0 24px #FF5A1F; }}
      #slam {{ position: absolute; left: 0; right: 0; top: 1130px; text-align: center; font: 900 170px/1 "Inter"; color: #F4F2EE; letter-spacing: -0.05em; }}
      #mark {{ position: absolute; left: 0; right: 0; top: 1390px; text-align: center; font: 900 210px/1 "Inter"; color: #FF6A33; letter-spacing: -0.04em; --st-glow: rgba(255,90,31,0.55); }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
      <div id="stage" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0">
        <div id="s1" class="scene">
          <div class="st-stage">
            <div class="st-layer" id="L-bg"><div id="grid"></div>
              <div class="blob" style="left:-260px; top:380px; width:1100px; height:1100px; background: radial-gradient(closest-side, rgba(255,90,31,0.32), rgba(255,90,31,0))"></div>
              <div class="blob" style="left:420px; top:1100px; width:1000px; height:1000px; background: radial-gradient(closest-side, rgba(107,75,255,0.22), rgba(107,75,255,0))"></div></div>
            <div class="st-layer" id="L-mid"><div id="ph-w"><div id="ph" class="st-elev-3 st-rim"><div class="scr st-sheen-host"><img src="assets/images/accueil.jpg" alt=""><div class="st-sheen" id="sheen"></div></div></div></div></div>
            <div class="st-layer" id="L-fg">{bokeh}</div>
          </div>
          <div class="st-layer" id="L-txt">
            <div class="kick" id="k1" style="top:170px">KOFA · BAMAKO</div>
            <div class="h" id="t1" style="top:240px">Le goût de Bamako,</div>
            <div class="h" id="t2" style="top:350px; color:#FF5A1F">livré chez vous.</div>
          </div>
        </div>
        <div id="s2" class="scene" style="opacity:0">
          <div class="pill st-elev-2 st-rim" style="top:520px"><i></i>Repas</div>
          <div class="pill st-elev-2 st-rim" style="top:690px"><i></i>Courses</div>
          <div class="pill st-elev-2 st-rim" style="top:860px"><i></i>Colis</div>
          <div id="slam" data-hf-motion-blur>Commandez.</div>
          <div id="mark" class="st-glow">KOFA</div>
        </div>
        <canvas id="grain" class="st-grain" width="{W}" height="{H}"></canvas>
        <div class="st-vignette"></div>
      </div>
      <audio id="sfx0" src="assets/whoosh.wav" data-start="4.35" data-duration="0.55" data-track-index="20" data-volume="0.5"></audio>
      <audio id="sfx1" src="assets/impact.wav" data-start="6.0" data-duration="1.2" data-track-index="21" data-volume="0.55"></audio>
      <audio id="sfx2" src="assets/riser.wav" data-start="5.6" data-duration="1.4" data-track-index="22" data-volume="0.25"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      (function () {{
        const S = STUDIO, $ = (q) => document.querySelector(q), $$ = (q) => Array.from(document.querySelectorAll(q));
        const tl = gsap.timeline({{ paused: true }});
        // scène 1 — caméra : grand angle incliné, mise au point sur le premier plan, puis travelling vers le téléphone
        S.camera(tl, [{{ el: $("#L-bg"), depth: 0.3 }}, {{ el: $("#L-mid"), depth: 1 }}, {{ el: $("#L-fg"), depth: 1.7 }}, {{ el: $("#L-txt"), depth: 0.35, blur: false }}], {{
          start: 0, end: 5.4, dof: {{ k: 10, max: 14 }}, drift: {{ x: 6, y: 5, r: 0.15, period: 8 }},
          keys: [{{ t: 0, s: 1.22, rx: 9, ry: -16, f: 1.75 }}, {{ t: 2.4, s: 1.0, rx: 0, ry: 0, f: 1.0 }}, {{ t: 5.4, s: 1.08, ry: 6, ease: S.ease.breath }}] }});
        tl.fromTo("#ph", {{ y: 160, rotation: -4 }}, {{ y: 0, rotation: 0, duration: S.dur.epic, ease: S.ease.silk }}, 0);
        S.life(tl, [$("#ph-w")], 1.6, 5.4, {{ y: 8, rotate: 0.4, period: 5 }});
        tl.fromTo("#k1", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: S.dur.base, ease: S.ease.swift }}, 0.25);
        S.rise(tl, S.split($("#t1")), 0.45, {{ y: 60, blur: 12, rotate: 6 }});
        S.maskUp(tl, S.split($("#t2"), {{ by: "words", mask: true }}), 1.15);
        S.sweep(tl, "#sheen", 2.6, {{ duration: 1.5 }});
        // transition — traversée vers la scène 2
        S.pushThrough(tl, "#s1", "#s2", 4.45, {{ duration: 0.8 }});
        // scène 2 — trois services sur ressort, puis le mot qui claque (flou de mouvement), puis la marque
        const pills = $$(".pill");
        S.pop(tl, pills, 5.0, {{ from: 0.4, y: 40, damping: 0.72, response: 0.5, stagger: 0.12 }});
        S.life(tl, pills, 5.6, 9.0, {{ y: 5, x: 2, rotate: 0.5, period: 4.5, seed: 8 }});
        tl.fromTo("#slam", {{ x: 1300, opacity: 1 }}, {{ x: 0, duration: 0.5, ease: S.ease.silk }}, 6.0);
        tl.fromTo("#slam", {{ scale: 1.06 }}, {{ scale: 1, duration: 0.6, ease: S.ease.swift, immediateRender: false }}, 6.35);
        S.converge(tl, S.split($("#mark")), 6.9, {{ spread: 90, blur: 22, duration: S.dur.hero }});
        // finitions — grain de film sur toute la durée
        S.drive(tl, 0, {TOTAL}, [S.grain($("#grain"), {{ fps: 25, seed: 4 }})]);
        tl.to({{}}, {{ duration: {TOTAL} }}, 0);
        window.__timelines["main"] = tl;
      }})();
    </script>
{MB}
  </body>
</html>
'''
open(f'{P}/index.html', 'w').write(html)
print('ok')
