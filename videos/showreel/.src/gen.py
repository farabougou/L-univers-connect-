# Showreel — Mohamed, motion design & vibe coding (Bamako). Vertical 1080×1920, 25 i/s, 104 temps à 124 BPM (50,3 s).
# Every cut lands on a beat of the score (.src/afrohouse.py). Shots are cut from the real renders in videos/*/renders
# (.src/shots.py). The overlay (one sub-composition) carries the type: hook, name, client labels, stats, end card.
import os, json, html, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shots import SHOTS
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1080, 1920
B = 60 / 124
T = lambda beats: round(beats * B, 3)
TOTAL = T(104)
ACC, INK, WHITE, MUTE = '#FF5A1F', '#0A0A0C', '#F4F2EE', '#8E8C94'

# ── edit decision list (beats) ──
FLASH = [('i1', 0, 1), ('i2', 1, 1), ('i3', 2, 1), ('i4', 3, 1)]
MONT_BEATS = [4, 4] + [2] * 16
MONT = []; b = 16
for k, n in zip([f'm{i:02d}' for i in range(1, 19)], MONT_BEATS): MONT.append((k, b, n)); b += n
assert b == 56
VIBE = []; b = 60
for k, n in [('v1', 4), ('v2', 4), ('v3', 2), ('v4', 2), ('v5', 2), ('v6', 2)]: VIBE.append((k, b, n)); b += n
assert b == 76
LABELS = [('m01', 'm02', 'SensExpress', 'Marketing olfactif'), ('m03', 'm05', "Founerou Grill's", 'Restauration · Ivry'),
          ('m06', 'm08', 'Cassia Dressing', 'Mode · Bamako'), ('m09', 'm10', 'GimSo', 'Mode Bogolan'),
          ('m11', 'm13', 'Enoryx', 'Énergie & bâtiments'), ('m14', 'm15', 'SK Print', 'Imprimerie'),
          ('m16', 'm16', 'Flèche Bamako', 'Animation 3D'), ('m17', 'm17', 'KTF Shipping', 'Logistique'),
          ('m18', 'm18', 'SensExpress', 'Diffuseurs de parfum'),
          ('v1', 'v5', 'KOFA', 'Mon app de livraison · Bamako'), ('v6', 'v6', 'KTF Shipping', 'Site web')]
WALL = [('w1', 'SensExpress'), ('w2', "Founerou Grill's"), ('w3', 'Cassia Dressing'), ('w4', 'GimSo'), ('w5', 'Enoryx'),
        ('w6', 'SK Print'), ('w7', 'Flèche Bamako'), ('w8', 'KTF Shipping'), ('w9', 'KOFA')]
start = {k: s for k, s, n in FLASH + MONT + VIBE}; length = {k: n for k, s, n in FLASH + MONT + VIBE}

# ── root video clips ──
vids, vjs = '', ''
for i, (k, s, n) in enumerate(FLASH + MONT + VIBE):
    vids += f'      <video id="v-{k}" class="clip shot" src="assets/clips/{k}.mp4" data-start="{T(s)}" data-duration="{T(n)}" data-track-index="{1 + i % 2}" muted playsinline></video>\n'
    # punch-in on every cut, a little bigger on section drops
    big = s in (16, 60)
    vjs += f'        tl.fromTo("#v-{k}", {{ scale: {1.14 if big else 1.07}, filter: "brightness({1.5 if big else 1.15})" }}, {{ scale: 1, filter: "brightness(1)", duration: {0.5 if big else 0.32}, ease: "power3.out" }}, {T(s)});\n'
    vjs += f'        tl.to("#v-{k}", {{ scale: 1.035, duration: {max(0.1, T(n) - 0.32)}, ease: "none" }}, {T(s) + 0.32:.3f});\n'
wall = ''
for i, (k, name) in enumerate(WALL):
    x, y = (i % 3) * 360, (i // 3) * 640
    wall += f'        <video id="v-{k}" class="clip tile" src="assets/clips/{k}.mp4" data-start="{T(84)}" data-duration="{T(8)}" data-track-index="{4 + i % 3}" muted playsinline style="left:{x + 6}px; top:{y + 6}px"></video>\n'
vjs += f'        tl.fromTo("#wall", {{ scale: 2.9 }}, {{ scale: 1, duration: {T(3)}, ease: "expo.out" }}, {T(84)});\n'
vjs += f'        tl.to("#wall", {{ scale: 0.94, duration: {T(5)}, ease: "none" }}, {T(87)});\n'
vjs += ''.join(f'        tl.fromTo("#v-{k}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.25, ease: "power2.out" }}, {T(84) + 0.05 * i:.3f});\n' for i, (k, n) in enumerate(WALL))

# ── overlay ──
CODE_SRC = open(f'{P}/../founerou-grill/.src/gen.py').read().split('\n')[20:120]
def code_rain(cid, n=70):
    rows = ''.join(f'<div data-layout-allow-overlap data-layout-allow-occlusion{" class='hot'" if (i * 7) % 11 == 0 else ""}>{html.escape(l) or "&nbsp;"}</div>' for i, l in enumerate(CODE_SRC[:n]))
    return f'<div class="rain" id="{cid}" data-layout-allow-overlap data-layout-allow-occlusion data-layout-allow-overflow>{rows}</div>'
lab_html, lab_js = '', ''
for j, (a, z, name, sector) in enumerate(LABELS):
    t0, t1 = T(start[a]), T(start[z] + length[z])
    lab_html += f'    <div class="chip" id="lb{j}"><b>{html.escape(name)}</b><span>{html.escape(sector)}</span></div>\n'
    lab_js += f'      tl.fromTo("#lb{j}", {{ opacity: 0, x: -60, filter: "blur(10px)" }}, {{ opacity: 1, x: 0, filter: "blur(0px)", duration: 0.35, ease: "expo.out" }}, {t0 + 0.08:.3f});\n'
    lab_js += f'      tl.to("#lb{j}", {{ opacity: 0, x: 40, duration: 0.18, ease: "power2.in" }}, {t1 - 0.2:.3f});\n'
wall_lab = ''.join(f'    <div class="wl" id="wl{i}" style="left:{(i % 3) * 360 + 16}px; top:{(i // 3) * 640 + 580}px">{html.escape(n)}</div>\n' for i, (k, n) in enumerate(WALL))

OVER = f'''<template>
  <style>
    @font-face {{ font-family: "Inter"; font-weight: 400; src: url("assets/fonts/inter-latin-400-normal.woff2") format("woff2"); }}
    @font-face {{ font-family: "Inter"; font-weight: 600; src: url("assets/fonts/inter-latin-600-normal.woff2") format("woff2"); }}
    @font-face {{ font-family: "Inter"; font-weight: 800; src: url("assets/fonts/inter-latin-800-normal.woff2") format("woff2"); }}
    @font-face {{ font-family: "Inter"; font-weight: 900; src: url("assets/fonts/inter-latin-900-normal.woff2") format("woff2"); }}
    @font-face {{ font-family: "Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }}
    #root {{ position: absolute; inset: 0; overflow: hidden; background: transparent; font-family: "Inter", sans-serif; }}
    .panel {{ position: absolute; inset: 0; background: {INK}; opacity: 0; }}
    .rain {{ position: absolute; left: 60px; top: 0; width: 1400px; font: 500 26px/40px "Plex Mono"; color: #3a3a44; white-space: pre; }}
    .rain .hot {{ color: #7a4a33; }}
    .fade {{ position: absolute; inset: 0; background: linear-gradient(180deg, {INK} 0%, rgba(10,10,12,0.55) 30%, rgba(10,10,12,0.55) 70%, {INK} 100%); }}
    .h {{ position: absolute; left: 0; right: 0; text-align: center; font-weight: 900; color: {WHITE}; letter-spacing: -0.04em; line-height: 0.95; white-space: nowrap; }}
    .h em {{ font-style: normal; color: {ACC}; }}
    .mono {{ font-family: "Plex Mono"; font-weight: 500; letter-spacing: 0; }}
    .cap {{ position: absolute; left: 0; right: 0; text-align: center; font: 600 30px "Inter"; letter-spacing: 0.32em; color: {MUTE}; text-transform: uppercase; white-space: nowrap; }}
    .w {{ display: inline-block; }}
    .chip {{ position: absolute; left: 48px; top: 96px; display: flex; flex-direction: column; gap: 6px; padding: 18px 26px 18px 30px; background: rgba(10,10,12,0.92); border-left: 6px solid {ACC}; border-radius: 6px; opacity: 0; }}
    .chip b {{ font: 800 40px "Inter"; color: {WHITE}; letter-spacing: -0.01em; }}
    .chip span {{ font: 500 24px "Inter"; color: #c8c6cc; letter-spacing: 0.04em; }}
    .tag {{ position: absolute; right: 48px; top: 116px; font: 500 22px "Plex Mono"; color: {WHITE}; letter-spacing: 0.12em; padding: 10px 16px; background: rgba(10,10,12,0.9); border: 1px solid rgba(244,242,238,0.3); border-radius: 6px; opacity: 0; }}
    .tag i {{ font-style: normal; color: #FF8A5C; }}
    .wl {{ position: absolute; font: 800 26px "Inter"; color: {WHITE}; padding: 6px 12px; background: rgba(10,10,12,0.72); border-radius: 4px; opacity: 0; white-space: nowrap; }}
    .stat {{ position: absolute; left: 0; right: 0; text-align: center; }}
    .stat b {{ display: block; font: 900 230px/0.9 "Inter"; color: {WHITE}; letter-spacing: -0.05em; }}
    .stat span {{ display: block; margin-top: 8px; font: 600 34px "Inter"; letter-spacing: 0.3em; color: {ACC}; text-transform: uppercase; }}
    #flash {{ position: absolute; inset: 0; background: {WHITE}; opacity: 0; }}
    #cur {{ display: inline-block; width: 0.08em; height: 0.8em; background: {ACC}; margin-left: 0.06em; vertical-align: -0.02em; }}
  </style>
  <div id="root" data-composition-id="overlay" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}">
    <div id="ov-clip" class="clip" data-start="0" data-duration="{TOTAL}" data-track-index="0" style="position:absolute; inset:0"></div>
    <!-- hook + name -->
    <div class="panel" id="p1">{code_rain('r1')}<div class="fade"></div></div>
    <div class="h" id="h1" style="top:660px; font-size:100px"><span class="w">Ces</span> <span class="w">pubs</span></div>
    <div class="h" id="h2" style="top:775px; font-size:96px"><span class="w">ne</span> <span class="w">sont</span> <span class="w">pas</span> <span class="w">montées.</span></div>
    <div class="h" id="h3" style="top:980px; font-size:100px"><span class="w">Elles</span> <span class="w">sont</span></div>
    <div class="h mono" id="h4" style="top:1110px; font-size:150px"><em>codées</em><span id="cur"></span></div>
    <div class="h" id="n1" style="top:770px; font-size:176px">MOHAMED</div>
    <div class="cap" id="n2" style="top:990px; color:{WHITE}">Motion design <span style="color:{ACC}">·</span> Vibe coding</div>
    <div class="cap" id="n3" style="top:1050px">Bamako · Mali</div>
    <!-- section tags -->
    <div class="tag" id="tg1"><i>01</i> · MOTION DESIGN</div>
    <div class="tag" id="tg2"><i>02</i> · VIBE CODING</div>
{lab_html}    <!-- vibe card -->
    <div class="panel" id="p2">{code_rain('r2')}<div class="fade"></div></div>
    <div class="h" id="c1" style="top:780px; font-size:130px"><span class="w">Et</span> <span class="w">je</span> <span class="w">code</span> <em class="w">aussi.</em></div>
    <div class="cap" id="c2" style="top:960px; color:{WHITE}">Apps · sites web · outils</div>
    <!-- stats -->
    <div class="panel" id="p3">{code_rain('r3')}<div class="fade"></div></div>
    <div class="stat" id="s1" style="top:330px"><b id="s1n">0</b><span>marques</span></div>
    <div class="stat" id="s2" style="top:800px"><b id="s2n">0</b><span>films</span></div>
    <div class="stat" id="s3" style="top:1270px"><b><span id="s3n" style="display:inline; font:inherit; letter-spacing:inherit; color:{ACC}; margin:0">0</span><span style="display:inline; font:inherit; letter-spacing:inherit; color:{ACC}; margin:0; text-transform:none">&nbsp;%</span></b><span>créés en code</span></div>
    <!-- wall labels -->
{wall_lab}    <!-- end -->
    <div class="panel" id="p4">{code_rain('r4')}<div class="fade"></div></div>
    <div class="cap" id="e0" style="top:600px; color:{ACC}">Votre marque est la prochaine</div>
    <div class="h" id="e1" style="top:710px; font-size:176px">MOHAMED</div>
    <div class="cap" id="e2" style="top:930px; color:{WHITE}">Motion design <span style="color:{ACC}">·</span> Vibe coding</div>
    <div class="cap" id="e3" style="top:990px">Bamako · Mali</div>
    <div id="flash"></div>
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
      const R = (s) => document.querySelector('[data-composition-id="overlay"] ' + s);
      const RA = (s) => document.querySelectorAll('[data-composition-id="overlay"] ' + s);
      // hook (beats 4–12): panel up, words land on the beat, code scrolls behind
      tl.set(R("#p1"), {{ opacity: 1 }}, {T(4)});
      tl.fromTo(R("#r1"), {{ y: 0 }}, {{ y: -1500, duration: {T(12)}, ease: "none" }}, {T(4)});
      const HW = [...RA("#h1 .w"), ...RA("#h2 .w"), ...RA("#h3 .w")];
      HW.forEach((w, i) => tl.fromTo(w, {{ opacity: 0, y: 40, filter: "blur(14px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.35, ease: "expo.out" }}, {T(4)} + i * {B / 2:.4f} + (i >= 6 ? {B:.4f} : 0)));
      tl.fromTo(R("#h4"), {{ opacity: 0, scale: 1.6, filter: "blur(20px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.45, ease: "expo.out" }}, {T(9)});
      tl.fromTo(R("#cur"), {{ opacity: 1 }}, {{ opacity: 0, duration: {B / 2:.4f}, ease: "steps(1)", repeat: 7, yoyo: true }}, {T(9)});
      tl.to([R("#h1"), R("#h2"), R("#h3"), R("#h4")], {{ opacity: 0, y: -50, filter: "blur(16px)", duration: 0.3, ease: "power2.in" }}, {T(12) - 0.3:.3f});
      // name (beats 12–16)
      tl.fromTo(R("#n1"), {{ opacity: 0, scale: 0.86, filter: "blur(18px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.9, ease: "expo.out" }}, {T(12)});
      tl.fromTo(R("#n2"), {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }}, {T(13)});
      tl.fromTo(R("#n3"), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, {T(14)});
      tl.to([R("#n1"), R("#n2"), R("#n3")], {{ opacity: 0, scale: 1.15, filter: "blur(16px)", duration: 0.25, ease: "power2.in" }}, {T(16) - 0.25:.3f});
      tl.set(R("#p1"), {{ opacity: 0 }}, {T(16)});
      // section tags + client labels
      tl.fromTo(R("#tg1"), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, {T(16)}); tl.to(R("#tg1"), {{ opacity: 0, duration: 0.2 }}, {T(56) - 0.2:.3f});
      tl.fromTo(R("#tg2"), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, {T(60)}); tl.to(R("#tg2"), {{ opacity: 0, duration: 0.2 }}, {T(76) - 0.2:.3f});
{lab_js.replace('"#lb', 'R("#lb').replace('", {', '"), {') if False else ''.join(l.replace('tl.fromTo("#', 'tl.fromTo(R("#').replace('tl.to("#', 'tl.to(R("#').replace('", {', '"), {') + chr(10) for l in lab_js.strip().split(chr(10)))}
      // vibe card (beats 56–60)
      tl.set(R("#p2"), {{ opacity: 1 }}, {T(56)});
      tl.fromTo(R("#r2"), {{ y: -200 }}, {{ y: -900, duration: {T(4)}, ease: "none" }}, {T(56)});
      RA("#c1 .w").forEach((w, i) => tl.fromTo(w, {{ opacity: 0, y: 40, filter: "blur(14px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.35, ease: "expo.out" }}, {T(56)} + i * {B / 2:.4f}));
      tl.fromTo(R("#c2"), {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, {T(58)});
      tl.to([R("#c1"), R("#c2")], {{ opacity: 0, scale: 1.2, filter: "blur(16px)", duration: 0.25, ease: "power2.in" }}, {T(60) - 0.25:.3f});
      tl.set(R("#p2"), {{ opacity: 0 }}, {T(60)});
      // stats (beats 76–84)
      tl.set(R("#p3"), {{ opacity: 1 }}, {T(76)});
      tl.fromTo(R("#r3"), {{ y: -600 }}, {{ y: -1400, duration: {T(8)}, ease: "none" }}, {T(76)});
      [["#s1", "#s1n", 9, 76], ["#s2", "#s2n", 19, 78], ["#s3", "#s3n", 100, 80]].forEach(([s, n, v, b]) => {{
        const t0 = b * {B:.6f}, el = R(n), c = {{ v: 0 }};
        tl.fromTo(R(s), {{ opacity: 0, y: 60, filter: "blur(16px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.45, ease: "expo.out" }}, t0);
        tl.fromTo(c, {{ v: 0 }}, {{ v: v, duration: 0.9, ease: "expo.out", onUpdate: () => {{ el.textContent = Math.round(c.v); }} }}, t0);
      }});
      tl.to([R("#s1"), R("#s2"), R("#s3")], {{ opacity: 0, scale: 0.9, filter: "blur(14px)", duration: 0.25, ease: "power2.in" }}, {T(84) - 0.25:.3f});
      tl.set(R("#p3"), {{ opacity: 0 }}, {T(84)});
      // wall labels (beats 84–92)
      RA(".wl").forEach((w, i) => {{ tl.fromTo(w, {{ opacity: 0, y: 12 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: "power3.out" }}, {T(86)} + i * 0.08); tl.to(w, {{ opacity: 0, duration: 0.2 }}, {T(92) - 0.2:.3f}); }});
      // end (beats 92–104)
      tl.fromTo(R("#p4"), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.2 }}, {T(92)});
      tl.fromTo(R("#r4"), {{ y: 0 }}, {{ y: -900, duration: {T(12)}, ease: "none" }}, {T(92)});
      tl.fromTo(R("#e0"), {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }}, {T(93)});
      tl.fromTo(R("#e1"), {{ opacity: 0, scale: 1.4, filter: "blur(20px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.8, ease: "expo.out" }}, {T(92)});
      tl.fromTo(R("#e2"), {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }}, {T(94)});
      tl.fromTo(R("#e3"), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, {T(95)});
      // white flash on the drops
      [16, 60, 84, 92].forEach((b) => tl.fromTo(R("#flash"), {{ opacity: 0.85 }}, {{ opacity: 0, duration: 0.28, ease: "power2.out", immediateRender: false }}, b * {B:.6f}));
      tl.to({{}}, {{ duration: {TOTAL} }}, 0);
      window.__timelines["overlay"] = tl;
    }})();
  </script>
</template>
'''
os.makedirs(f'{P}/compositions', exist_ok=True)
open(f'{P}/compositions/overlay.html', 'w').write(OVER)
SFX = [('impact', T(0), 0.5), ('riser', T(10.5), 0.35), ('impact', T(16), 0.6), ('whoosh', T(56) - 0.1, 0.4), ('riser', T(57), 0.3),
       ('impact', T(60), 0.55), ('impact', T(76), 0.4), ('impact', T(84), 0.6), ('impact', T(92), 0.55)]
import soundfile as _sf
LEN = {n: round(_sf.info(f'{P}/assets/{n}.wav').duration, 2) for n in ('impact', 'whoosh', 'riser')}
sfx = ''.join(f'      <audio id="sfx{i}" src="assets/{f}.wav" data-start="{t}" data-duration="{LEN[f]}" data-track-index="{20 + i % 4}" data-volume="{v}"></audio>\n' for i, (f, t, v) in enumerate(SFX))
idx = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {INK}; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {INK}; }}
      .shot {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; object-fit: cover; }}
      #wall {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; transform-origin: 540px 960px; }}
      .tile {{ position: absolute; width: 348px; height: 628px; object-fit: cover; border-radius: 10px; }}
      .scene {{ position: absolute; inset: 0; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="{W}" data-height="{H}" data-fps="25">
{vids}      <div id="wall">
{wall}      </div>
      <div id="el-overlay" class="scene" data-composition-id="overlay" data-composition-src="compositions/overlay.html" data-start="0" data-duration="{TOTAL}" data-track-index="8"></div>
      <audio id="el-bgm" src="assets/music.wav" data-start="0" data-duration="{TOTAL}" data-track-index="15" data-volume="0.9"></audio>
{sfx}    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
      (function () {{ var tl = window.__timelines["main"];
{vjs}        tl.to({{}}, {{ duration: {TOTAL} }}, 0);
      }})();
    </script>
  </body>
</html>
'''
open(f'{P}/index.html', 'w').write(idx)
print('ok', TOTAL)
