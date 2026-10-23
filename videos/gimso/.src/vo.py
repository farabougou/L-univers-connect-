# Place the client's ElevenLabs voiceover (Anna, 22.1 s) on the GimSo ad: each phrase lands on its shot. Writes assets/voice + voice.json.
import os, json, sys, soundfile as sf
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
x, sr = sf.read(sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-0/gimso/vo/v.wav')
# (start, end) in the recording → start time in the film
CL = [(0.02, 3.30, 0.15),   # Le Bogolan… comme vous ne l'avez jamais porté.
      (3.45, 5.00, 3.95),   # GimSo, Chez Madame.
      (5.20, 6.63, 7.35),   # Des capes à capuche,
      (6.63, 7.67, 10.3),   # des ponchos amples, en blanc
      (7.67, 9.10, 13.3),   # ou en noir…
      (9.25, 11.82, 16.3),  # et des gilets à franges, pour un style unique.
      (11.98, 14.98, 19.4), # Pour compléter le look : casquettes et sacs en Bogolan.
      (15.08, 17.97, 23.15),# Plus de trois cent mille personnes nous suivent déjà sur TikTok.
      (18.05, len(x) / sr, 26.6)]  # Commandez maintenant au 76 67 03 42.
os.makedirs(f'{P}/assets/voice', exist_ok=True)
out = []
for i, (a, b, at) in enumerate(CL):
    clip = x[int(a * sr):int(b * sr)].copy()
    n = int(0.02 * sr); clip[:n] *= [k / n for k in range(n)]; clip[-n:] *= [1 - k / n for k in range(n)]
    sf.write(f'{P}/assets/voice/{i + 1:02d}.wav', clip, sr)
    out.append([f'assets/voice/{i + 1:02d}.wav', at, round(len(clip) / sr, 2)])
json.dump(out, open(f'{P}/assets/voice/voice.json', 'w'), indent=1)
print(out)
