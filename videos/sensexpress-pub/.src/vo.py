# Place the client's ElevenLabs voiceover (Anna, 24.7 s) on the 40 s product ad. On-screen text carries every phrase.
import os, soundfile as sf
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
x, sr = sf.read('/tmp/claude-0/sxpv/v.wav')
# (start, end) in the recording → where it starts in the film
CL = [(0.07, 2.15, 1.0),     # Et si votre marque avait un parfum ?
      (2.50, 6.62, 5.0),     # Ne vous contentez plus de faire parler de vos produits : faites sentir votre marque.
      (6.80, 11.95, 10.5),   # L'Héritier, notre diffuseur intelligent, parfume votre espace au bon moment, sans gaspillage.
      (12.04, 17.08, 16.9),  # La Princesse, la Duchesse, le Prince, la Reine : une collection pour chaque volume.
      (17.20, 19.40, 24.6),  # Et des parfums signature, pour chaque lieu.
      (19.54, 22.20, 30.8),  # Hôtels, bureaux, maison, voiture.
      (22.46, 24.69, 34.7)]  # SensExpress. Éveillez vos sens.
os.makedirs(f'{P}/assets/voice', exist_ok=True)
aud = ''
for i, (a, b, at) in enumerate(CL):
    clip = x[int(a * sr):int(b * sr)]
    sf.write(f'{P}/assets/voice/{i + 1:02d}.wav', clip, sr)
    aud += f'      <audio id="el-vo{i + 1}" src="assets/voice/{i + 1:02d}.wav" data-start="{at - 0.05}" data-duration="{round(len(clip) / sr, 2)}" data-track-index="{20 + i}" data-volume="1"></audio>\n'
s = open(f'{P}/index.html').read()
s = s.replace('id="el-bgm" src="assets/music.wav" data-start="0" data-duration="40" data-track-index="11" data-volume="0.6"', 'id="el-bgm" src="assets/music.wav" data-start="0" data-duration="40" data-track-index="11" data-volume="0.18"')
s = s.replace('data-volume="0.3"></audio>', 'data-volume="0.2"></audio>')
assert 'el-vo1' not in s
s = s.replace('    </div>\n    <script>', aud + '    </div>\n    <script>', 1)
open(f'{P}/index.html', 'w').write(s)
print('ok')
