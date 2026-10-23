# Add the ElevenLabs voiceover (one clip per sequence) + sentence captions to a KTF project.
import sys, os, re, soundfile as sf
P, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
x, sr = sf.read('/tmp/claude-0/ktfv/v.wav')
# detected speech runs in the recording (s) and their text
SEG = [(0.07, 2.5, "Un trajet clair commence par de bons repères."),
       (2.86, 6.56, "Sur le site de KTF Shipping, le design organise la découverte."),
       (6.91, 10.95, "Des titres affirmés, des contrastes nets, une couleur qui guide le regard."),
       (11.31, 14.09, "Chaque service prend sa place dans une interface structurée."),
       (14.37, 19.34, "On explore les modes de transport, on consulte les départs, puis on accède à l'espace de suivi."),
       (19.67, 23.48, "La navigation relie les informations utiles et conduit vers la demande de devis."),
       (23.79, 28.22, "Du premier écran au dernier bouton, les mêmes repères visuels accompagnent la lecture."),
       (28.62, 29.55, "KTF Shipping :"),
       (29.87, 33.23, "découvrez un univers de transport, pensé pour être parcouru."),
       (33.52, 36.0, "Rendez-vous sur ktf-shipping.com.")]
# recording cut points per film sequence, and where each clip starts in the film
GRP = [(0.0, 6.75, 0.3), (6.75, 11.15, 7.4), (11.15, 14.25, 16.6), (14.25, 19.5, 27.5), (19.5, 28.45, 38.4), (28.45, len(x) / sr, 50.3)]
os.makedirs(f'{P}/assets/voice', exist_ok=True)
aud, caps = '', []
for i, (a, b, at) in enumerate(GRP):
    seg = x[int(a * sr):int(b * sr)]
    sf.write(f'{P}/assets/voice/{i + 1:02d}.wav', seg, sr)
    aud += f'      <audio id="el-vo{i + 1}" src="assets/voice/{i + 1:02d}.wav" data-start="{at}" data-duration="{round(len(seg) / sr, 2)}" data-track-index="{20 + i}" data-volume="1"></audio>\n'
    for s, e, t in SEG:
        if a <= s < b: caps.append((round(at + s - a, 2), min(56.0, round(at + e - a + 0.15, 2)), t))
# merge the short "KTF Shipping :" with the next sentence on screen
m = []
for c in caps:
    if m and m[-1][2].endswith(':'): m[-1] = (m[-1][0], c[1], m[-1][2] + ' ' + c[2])
    else: m.append(c)
land = W > H
fs, mw, bot = (38, 1400, 54) if land else (38, 1000, 110)
items = ''.join(f'    <div class="cap" id="cap{i}"><span>{t}</span></div>\n' for i, (s, e, t) in enumerate(m))
tw = ''.join(f'      tl.fromTo("#cap{i}", {{ opacity: 0, y: 12 }}, {{ opacity: 1, y: 0, duration: 0.25, ease: "power2.out" }}, {s});\n      tl.to("#cap{i}", {{ opacity: 0, duration: 0.2 }}, {e});\n' for i, (s, e, t) in enumerate(m))
open(f'{P}/compositions/captions.html', 'w').write(f'''<template>
  <style>
    @font-face {{ font-family: "Roboto"; font-weight: 500; src: url("assets/fonts/roboto-latin-500-normal.woff2") format("woff2"); }}
    [data-composition-id="captions"] .cap {{ position: absolute; left: 0; right: 0; bottom: {bot}px; display: flex; justify-content: center; opacity: 0; }}
    [data-composition-id="captions"] .cap span {{ display: block; max-width: {mw}px; padding: 12px 26px; border-radius: 10px; background: rgba(6,17,31,0.86); font-family: "Roboto"; font-weight: 500; font-size: {fs}px; line-height: 1.35; text-align: center; color: #FFFFFF; }}
  </style>
  <div id="root" data-composition-id="captions" data-start="0" data-duration="60" data-width="{W}" data-height="{H}" style="position:absolute; inset:0">
{items}  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
{tw}      tl.to({{}}, {{ duration: 60 }}, 0);
      window.__timelines["captions"] = tl;
    }})();
  </script>
</template>
''')
s = open(f'{P}/index.html').read()
s = s.replace('data-volume="0.55"', 'data-volume="0.28"')
cap = f'      <div id="el-captions" class="scene" data-track-kind="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="60" data-track-index="2"></div>\n'
s = s.replace('    </div>\n    <script>', aud + cap + '    </div>\n    <script>', 1)
open(f'{P}/index.html', 'w').write(s)
print(len(m), 'captions;', [c[:2] for c in m])
