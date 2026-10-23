# Place the client's ElevenLabs voiceover (Anna) on the SensExpress film + sentence captions.
import os, soundfile as sf
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
x, sr = sf.read('/tmp/claude-0/sensv/v.wav')
# (start, end) of each spoken sentence in the recording, its text, and where it lands in the film
SEG = [(0.07, 2.66, "Une marque se reconnaît aussi à ce qu'elle fait ressentir.", 0.5),
       (2.99, 5.75, "Avec SensExpress, cet univers prend forme à l'écran.", 3.3),
       (6.10, 7.66, "Le noir pose le décor.", 6.5),
       (7.94, 9.70, "Le doré attire le regard.", 8.5),
       (10.04, 13.38, "Les titres et les images invitent à découvrir les solutions olfactives.", 10.6),
       (13.72, 18.64, "Hôtels, bureaux, maison et voiture : chaque espace ouvre sur une gamme à explorer.", 14.2),
       (19.00, 23.14, "Le site présente les diffuseurs et vous guide vers un conseiller pour parler de votre projet.", 25.4),
       (23.46, 24.36, None, 36.4),     # « SensExpress. »         — written in the logo on screen
       (24.65, 25.64, None, 37.3),     # « Éveillez vos sens. »   — written in the logo on screen
       (25.90, 28.46, None, 38.7)]     # « … sur sensexpress.com » — the address alone stays on screen (brief)
os.makedirs(f'{P}/assets/voice', exist_ok=True)
aud, items, tw = '', '', ''
for i, (a, b, text, at) in enumerate(SEG):
    a0, b0 = max(0, a - 0.05), min(len(x) / sr, b + 0.12)
    clip = x[int(a0 * sr):int(b0 * sr)]
    sf.write(f'{P}/assets/voice/{i + 1:02d}.wav', clip, sr)
    aud += f'      <audio id="el-vo{i + 1}" src="assets/voice/{i + 1:02d}.wav" data-start="{round(at - 0.05, 2)}" data-duration="{round(len(clip) / sr, 2)}" data-track-index="{20 + i}" data-volume="1"></audio>\n'
    if text:
        s, e = round(at, 2), round(at + (b - a) + 0.2, 2)
        items += f'    <div class="cap" id="cap{i}"><span>{text}</span></div>\n'
        tw += f'      tl.fromTo("#cap{i}", {{ opacity: 0, y: 10 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: "power2.out" }}, {s});\n      tl.to("#cap{i}", {{ opacity: 0, duration: 0.25 }}, {e});\n'
open(f'{P}/compositions/captions.html', 'w').write(f'''<template>
  <style>
    @font-face {{ font-family: "Montserrat"; font-weight: 500; src: url("assets/fonts/montserrat-latin-500-normal.woff2") format("woff2"); }}
    [data-composition-id="captions"] .cap {{ position: absolute; left: 0; right: 0; bottom: 188px; display: flex; justify-content: center; opacity: 0; }}
    [data-composition-id="captions"] .cap span {{ display: block; max-width: 880px; font-family: "Montserrat"; font-weight: 500; font-size: 34px; line-height: 1.36; text-align: center; color: #FFFFFF; padding: 10px 24px; border-radius: 10px; background: rgba(0,0,0,0.62); }}
  </style>
  <div id="root" data-composition-id="captions" data-start="0" data-duration="42" data-width="1080" data-height="1920" style="position:absolute; inset:0">
{items}  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
{tw}      tl.to({{}}, {{ duration: 42 }}, 0);
      window.__timelines["captions"] = tl;
    }})();
  </script>
</template>
''')
s = open(f'{P}/index.html').read()
s = s.replace('id="el-bgm" src="assets/music.wav" data-start="0" data-duration="42" data-track-index="11" data-volume="0.6"', 'id="el-bgm" src="assets/music.wav" data-start="0" data-duration="42" data-track-index="11" data-volume="0.18"')
cap = '      <div id="el-captions" class="scene" data-track-kind="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="42" data-track-index="2"></div>\n'
assert 'el-captions' not in s
s = s.replace('    </div>\n    <script>', aud + cap + '    </div>\n    <script>', 1)
open(f'{P}/index.html', 'w').write(s)
print('ok')
