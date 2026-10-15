# Place the client's ElevenLabs voiceover (Anna, 27.6 s) on the Cassia ad: one clip per scene, written to assets/voice + voice.json.
import os, json, sys, soundfile as sf
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
x, sr = sf.read(sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-0/cassia/vo/v.wav')
# (start, end) in the recording → start time in the film
CL = [(0.02, 2.40, 0.6),    # Cassia Dressing présente sa nouvelle collection.
      (2.60, 6.40, 4.9),    # Le Bogolan, notre héritage… réinventé pour aujourd'hui.
      (6.66, 10.28, 9.7),   # Des chemises tradi-modernes, élégantes et pleines de caractère.
      (10.40, 12.92, 15.9), # Des vestes au style urbain, signées Cassia.
      (13.10, 16.78, 20.75),# Et pour madame, des robes en tissu Diaz, fluides et raffinées.
      (16.92, 20.08, 25.6), # Modernité et authenticité, pour toutes vos occasions.
      (20.22, 22.75, 29.4), # Affirmez votre classe avec Cassia Dressing.
      (22.88, len(x) / sr, 32.1)]  # Commandez dès maintenant au 94 55 85 40.
os.makedirs(f'{P}/assets/voice', exist_ok=True)
out = []
for i, (a, b, at) in enumerate(CL):
    clip = x[int(a * sr):int(b * sr)]
    n = int(0.03 * sr); clip[:n] *= [k / n for k in range(n)]; clip[-n:] *= [1 - k / n for k in range(n)]
    sf.write(f'{P}/assets/voice/{i + 1:02d}.wav', clip, sr)
    out.append([f'assets/voice/{i + 1:02d}.wav', at, round(len(clip) / sr, 2)])
json.dump(out, open(f'{P}/assets/voice/voice.json', 'w'), indent=1)
print(out)
