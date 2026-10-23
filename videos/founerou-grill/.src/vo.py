# Place the client's ElevenLabs voiceover (Anna, 28.2 s) on the Founerou Grill's ad. Writes assets/voice + voice.json.
import os, json, sys, soundfile as sf
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
x, sr = sf.read(sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-0/fgrill/vo/v.wav')
# (start, end) in the recording → start time in the film (scene starts: 0, 3.6, 8.4, 14.2, 21.6, 25.6, 29.2, 33.4)
CL = [(0.00, 1.40, 0.30),    # Ça grille à Ivry !
      (1.42, 3.85, 4.00),    # La brochette… à un euro seulement !  (« un euro » on the 1€ slam)
      (3.95, 9.55, 8.45),    # Le menu : une cuisse ou trois pilons, un accompagnement et une boisson… six euros quatre-vingt-dix.
      (9.70, 14.20, 14.65),  # Poulet, ailes, pilons, saucisse, brick, donuts : tout droit du grill.
      (14.30, 17.80, 21.95), # Pâtes au poulet, riz thaï ou alloco : trois euros la barquette.
      (17.82, 19.80, 25.95), # Jus de bissap, jus de gingembre…
      (19.84, 24.10, 29.35), # Certifié halal, ouvert sept jours sur sept, de onze heures à deux heures du matin.
      (24.18, len(x) / sr, 33.60)]  # Founerou Grill's, 72 boulevard de Brandebourg, à Ivry-sur-Seine.
os.makedirs(f'{P}/assets/voice', exist_ok=True)
out = []
for i, (a, b, at) in enumerate(CL):
    clip = x[int(a * sr):int(b * sr)].copy()
    n = int(0.015 * sr); clip[:n] *= [k / n for k in range(n)]; clip[-n:] *= [1 - k / n for k in range(n)]
    sf.write(f'{P}/assets/voice/{i + 1:02d}.wav', clip, sr)
    out.append([f'assets/voice/{i + 1:02d}.wav', at, round(len(clip) / sr, 2)])
json.dump(out, open(f'{P}/assets/voice/voice.json', 'w'), indent=1)
for o in out: print(o, 'ends', round(o[1] + o[2], 2))
