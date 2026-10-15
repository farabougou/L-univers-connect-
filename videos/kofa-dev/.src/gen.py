# KOFA — reel « dev à l'écran » v2 : la vraie photo du bureau de Mohamed (HP Pavilion) ; sur la dalle, l'enregistrement
# d'écran videos/kofa-ecran (VS Code + iPhone 15 Pro Max, frappe humaine, accueil KOFA construit en direct) projeté par
# homographie (matrix3d). Trois extraits montés avec des mouvements de caméra. Vertical 1080×1920, 25 i/s, 31 s.
# (v1, avec l'écran dessiné en HTML : .src/gen_v1.py)
import os, json
import numpy as np
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, TOTAL = 1080, 1920, 31
ORANGE, BLUE = '#EB6834', '#2A78D6'

# ── screen homography: 1920×1080 screen → photo (photo resized 1500×2000 → 1440×1920) ──
S = 0.96
QUAD = [(-40, -5), (1768, -83), (1535, 923), (195, 937)]  # TL TR BR BL, measured on the original photo
Q = [(x * S, y * S) for x, y in QUAD]
def homog(src, dst):
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]; b += [u, v]
    h = np.linalg.solve(np.array(A, float), np.array(b, float)); return np.append(h, 1).reshape(3, 3)
HM = homog([(0, 0), (1920, 0), (1920, 1080), (0, 1080)], Q)
M3D = 'matrix3d(' + ','.join(f'{v:.9g}' for v in [HM[0, 0], HM[1, 0], 0, HM[2, 0], HM[0, 1], HM[1, 1], 0, HM[2, 1], 0, 0, 1, 0, HM[0, 2], HM[1, 2], 0, HM[2, 2]]) + ')'
def to_photo(x, y):
    u = HM @ np.array([x, y, 1.0]); return float(u[0] / u[2]), float(u[1] / u[2])

# ── three excerpts of the recording: (film start, duration, media start)
# saves in the recording: 31.44 title, 35.13 search, 46.77 categories, 53.06 restaurants, 62.77 promos, 66.58 tab bar
SEGS = [(0.0, 8.6, 28.6), (8.6, 10.4, 44.6), (19.0, 7.6, 61.4)]
phone_c = to_photo(380, 520)
code_c = to_photo(1260, 640)
wide = (600, 960)
def cam(pt, k, oy=960, ox=540):
    return {'x': round(ox - k * pt[0], 1), 'y': round(oy - k * pt[1], 1), 'scale': k}
CAM = [(0.0, cam(wide, 1.0)), (3.0, cam(wide, 1.06, 980)), (4.2, cam(code_c, 1.9, 860)), (8.6, cam(code_c, 2.05, 860)),
       (8.6, cam(phone_c, 2.15, 900)), (13.5, cam(phone_c, 2.3, 880)), (14.6, cam(code_c, 1.85, 880)), (19.0, cam(code_c, 1.95, 880)),
       (19.0, cam(phone_c, 1.9, 900)), (23.6, cam(phone_c, 2.1, 890)), (24.8, cam(wide, 1.0)), (31.0, cam(wide, 1.04))]
cam_js = f'      gsap.set("#cam", {json.dumps(CAM[0][1])});\n'
for (t0, a), (t1, b) in zip(CAM, CAM[1:]):
    if t1 == t0:   # hard cut: the camera jumps on the edit
        cam_js += f'      tl.set("#cam", {json.dumps(b)}, {t0});\n'; continue
    ease = 'power2.inOut' if abs(a['scale'] - b['scale']) > 0.3 or abs(a['x'] - b['x']) > 200 else 'none'
    cam_js += f'      tl.fromTo("#cam", {json.dumps(a)}, {{ ...{json.dumps(b)}, duration: {round(t1 - t0, 2)}, ease: "{ease}", immediateRender: false }}, {t0});\n'
vids = ''.join(f'          <video id="scr{i}" class="clip scr" src="assets/clips/ecran.mp4" data-start="{st}" data-duration="{d}" data-media-start="{ms}" data-track-index="{1 + i}" muted playsinline></video>\n' for i, (st, d, ms) in enumerate(SEGS))
whip = ''.join(f'      tl.fromTo("#cam", {{ filter: "blur(10px)" }}, {{ filter: "blur(0px)", duration: 0.22, ease: "power2.out", immediateRender: false }}, {st});\n' for st, d, ms in SEGS[1:])
END = 26.2

idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Inter"; font-weight: 800; src: url("assets/fonts/inter-latin-800-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 900; src: url("assets/fonts/inter-latin-900-normal.woff2") format("woff2"); }}
      @font-face {{ font-family: "Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #000; font-family: "Inter", sans-serif; }}
      #film {{ position: absolute; inset: 0; }}
      #cam {{ position: absolute; left: 0; top: 0; width: 1440px; height: 1920px; transform-origin: 0 0; }}
      #photo {{ position: absolute; left: 0; top: 0; width: 1440px; height: 1920px; filter: brightness(0.5) contrast(1.12) saturate(0.55) sepia(0.15); }}
      .scr {{ position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; transform-origin: 0 0; transform: {M3D}; object-fit: fill; }}
      #glow {{ position: absolute; left: 0; top: 760px; width: 1440px; height: 1160px; background: radial-gradient(60% 45% at 50% 18%, rgba(110,140,255,0.22), rgba(235,104,52,0.06) 55%, rgba(0,0,0,0) 80%); mix-blend-mode: screen; }}
      #vig {{ position: absolute; inset: 0; background: radial-gradient(75% 60% at 50% 42%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.75) 100%); }}
      #grain {{ position: absolute; left: -200px; top: -200px; width: 1480px; height: 2320px; background: url(assets/images/grain.png); opacity: 0.07; mix-blend-mode: overlay; }}
      #cap {{ position: absolute; left: 0; right: 0; top: 230px; text-align: center; }}
      #cap span {{ display: inline-block; padding: 18px 34px; border-radius: 18px; background: rgba(10,10,12,0.72); font: 800 46px/1.2 "Inter"; color: #fff; letter-spacing: -0.01em; }}
      #cap em {{ font-style: normal; color: {ORANGE}; }}
      #end {{ position: absolute; inset: 0; background: rgba(8,8,10,0.86); opacity: 0; }}
      .klogo {{ width: 150px; height: 150px; border-radius: 40px; background: {BLUE}; color: #fff; font: 900 100px/150px "Inter"; text-align: center; }}
      #endk {{ position: absolute; left: 0; right: 0; top: 700px; display: flex; justify-content: center; align-items: center; gap: 28px; }}
      #endk b {{ font: 900 150px/1 "Inter"; color: #fff; letter-spacing: -0.04em; }}
      #e1 {{ top: 930px; font: 800 58px/1.15 "Inter"; color: #fff; letter-spacing: -0.02em; }}
      #e1 em {{ font-style: normal; color: {ORANGE}; }}
      #e2 {{ position: absolute; left: 140px; top: 1110px; width: 800px; height: 96px; border-radius: 48px; background: {ORANGE}; font: 800 40px/96px "Inter"; color: #fff; text-align: center; }}
      #e3 {{ top: 1250px; font: 500 30px "Plex Mono"; color: #c9c9d2; letter-spacing: 0.06em; }}
      .c {{ position: absolute; left: 0; right: 0; text-align: center; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
      <div id="film">
        <div id="cam">
          <img id="photo" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" src="assets/images/bureau.jpg" alt="">
{vids}          <div id="glow"></div>
        </div>
        <div id="vig" data-layout-allow-occlusion></div>
        <div id="grain" data-layout-allow-occlusion data-layout-allow-overflow></div>
        <div id="cap" data-layout-allow-overlap><span>Je code <em>KOFA</em>, l'app de livraison<br>de Bamako</span></div>
        <div id="end" data-layout-allow-occlusion></div>
        <div id="endk"><div class="klogo">K</div><b>KOFA</b></div>
        <div class="c" id="e1">Le goût de Bamako,<br><em>livré chez vous.</em></div>
        <div id="e2">Bientôt disponible à Bamako</div>
        <div class="c" id="e3">kofa.ml</div>
      </div>
      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="9" data-volume="0.8"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
{cam_js}{whip}      tl.fromTo("#photo", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.8, ease: "power1.out" }}, 0);
      tl.fromTo("#grain", {{ x: 0, y: 0 }}, {{ x: -180, y: -140, duration: {TOTAL}, ease: "steps({TOTAL * 25})" }}, 0);
      tl.fromTo("#cap span", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }}, 0.4);
      tl.to("#cap span", {{ opacity: 0, y: -16, duration: 0.4, ease: "power2.in" }}, 3.6);
      tl.fromTo("#end", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.7, ease: "power2.out" }}, {END});
      tl.fromTo("#endk", {{ opacity: 0, scale: 0.85 }}, {{ opacity: 1, scale: 1, duration: 0.6, ease: "back.out(1.6)" }}, {END + 0.4});
      tl.fromTo("#e1", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }}, {END + 0.9});
      tl.fromTo("#e2", {{ opacity: 0, scale: 0.8 }}, {{ opacity: 1, scale: 1, duration: 0.5, ease: "back.out(1.8)" }}, {END + 1.5});
      tl.fromTo("#e3", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, {END + 2.0});
      tl.set({{}}, {{}}, {TOTAL});
    </script>
  </body>
</html>
'''
open(f'{P}/index.html', 'w').write(idx)
print('ok', TOTAL, 'phone', [round(v) for v in phone_c], 'code', [round(v) for v in code_c])
